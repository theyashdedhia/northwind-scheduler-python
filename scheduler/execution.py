"""Run a complete request in a disposable process with a wall-clock budget."""

import multiprocessing
import pickle
from pathlib import Path
import tempfile
from time import monotonic

from .model import FakeModel

MAX_RESULT_BYTES = 8 * 1024 * 1024
CLEANUP_SECONDS = 0.1


class RequestDeadlineExceeded(Exception):
    pass


def _execute(agent, request: str, result_path: str) -> None:
    answer = agent._run(request)
    # Script consumption and call snapshots remain observable in existing fake tests.
    fake_state = ((agent.model.script, agent.model.calls)
                  if isinstance(agent.model, FakeModel) else None)
    result = (answer, agent.turns, agent.attendees, fake_state)
    with open(result_path, "wb") as output:
        pickle.dump(result, output)


def execute_request(agent, request: str) -> tuple:
    """Include startup and the whole agent loop in one deadline; reap on all exits.

    Fork preserves local fake implementations on POSIX. Other platforms use
    spawn and require a picklable model. Result files avoid blocking pipe reads
    and are read only after the worker exits successfully.
    """
    deadline = monotonic() + agent.timeout_seconds
    method = "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"
    context = multiprocessing.get_context(method)
    with tempfile.TemporaryDirectory(prefix="northwind-request-") as directory:
        result_path = Path(directory) / "result.pkl"
        worker = context.Process(target=_execute, args=(agent, request, str(result_path)), daemon=True)
        try:
            worker.start()
            worker.join(max(0, deadline - monotonic()))
            if worker.is_alive() or monotonic() >= deadline:
                raise RequestDeadlineExceeded
            if worker.exitcode != 0 or not result_path.exists():
                raise RuntimeError("Request worker failed.")
            if result_path.stat().st_size > MAX_RESULT_BYTES:
                raise RuntimeError("Request result exceeds the size limit.")
            with result_path.open("rb") as source:
                return pickle.load(source)
        finally:
            if worker.pid is not None:
                if worker.is_alive():
                    worker.terminate()
                    worker.join(CLEANUP_SECONDS)
                if worker.is_alive():
                    worker.kill()
                    worker.join(CLEANUP_SECONDS)
                if not worker.is_alive():
                    worker.close()
