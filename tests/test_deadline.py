"""Real process cancellation tests using fake models; no network access."""

import multiprocessing
import os
import signal
import threading
import time

import pytest

from scheduler import agent as agent_module
from scheduler.agent import SchedulingAgent
from scheduler.model import FakeModel, final, tool_call
from scheduler.store import Store


class BlockingFakeModel(FakeModel):
    def complete(self, messages):
        threading.Event().wait()


class SlowFakeModel(FakeModel):
    def complete(self, messages):
        time.sleep(0.06)
        return super().complete(messages)


class BlockFinalFakeModel(FakeModel):
    def complete(self, messages):
        if messages[-1]["role"] == "tool":
            threading.Event().wait()
        return super().complete(messages)


class IgnoreTerminationFakeModel(FakeModel):
    def complete(self, messages):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        threading.Event().wait()


class ExitFakeModel(FakeModel):
    def complete(self, messages):
        os._exit(1)


def active_pids():
    return {child.pid for child in multiprocessing.active_children()}


def test_blocked_model_is_cancelled_and_reaped():
    before = active_pids()
    agent = SchedulingAgent(BlockingFakeModel([]), Store.load(), timeout_seconds=0.1)
    started = time.monotonic()
    assert "timed out" in agent.run("Find a time")
    assert time.monotonic() - started < 1
    assert active_pids() == before
    # A cancelled worker does not prevent the next request from completing.
    agent.model = FakeModel([tool_call("list_people"), final("done")])
    agent.timeout_seconds = 2
    assert "Employees:" in agent.run("list people")


def test_deadline_is_shared_across_model_calls():
    model = SlowFakeModel([tool_call("list_people")], loop_last=True)
    agent = SchedulingAgent(model, Store.load(), timeout_seconds=0.15)
    started = time.monotonic()
    assert "timed out" in agent.run("Find a time")
    assert time.monotonic() - started < 1


def test_timeout_does_not_commit_partial_attendees_or_answer():
    agent = SchedulingAgent(FakeModel([
        tool_call("find_free_slots", attendees=["sam"], date="2026-11-03", duration_minutes=30),
        final("done"),
    ]), Store.load())
    agent.run("Find 30 minutes with Sam on Tuesday")
    previous_turn = agent.turns[-1]
    agent.model = BlockFinalFakeModel([
        tool_call("find_free_slots", attendees=["mei"], date="2026-11-03", duration_minutes=30),
    ])
    agent.timeout_seconds = 0.1
    assert "timed out" in agent.run("What about Mei?")
    assert agent.attendees == ["sam"]
    assert agent.turns[-2] == previous_turn
    assert "Availability for" not in agent.turns[-1][-1]["content"]


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="Local tool override requires fork")
def test_blocked_tool_is_also_cancelled(monkeypatch):
    def blocked_tool(store):
        threading.Event().wait()

    monkeypatch.setitem(agent_module.TOOLS, "list_people", blocked_tool)
    before = active_pids()
    agent = SchedulingAgent(FakeModel([tool_call("list_people")]), Store.load(), timeout_seconds=0.1)
    assert "timed out" in agent.run("list people")
    assert active_pids() == before


@pytest.mark.skipif(os.name != "posix", reason="POSIX signal handling")
def test_worker_ignoring_termination_is_killed_and_reaped():
    before = active_pids()
    agent = SchedulingAgent(IgnoreTerminationFakeModel([]), Store.load(), timeout_seconds=0.1)
    started = time.monotonic()
    assert "timed out" in agent.run("Find a time")
    assert time.monotonic() - started < 1
    assert active_pids() == before


def test_abrupt_worker_exit_returns_controlled_failure():
    before = active_pids()
    agent = SchedulingAgent(ExitFakeModel([]), Store.load(), timeout_seconds=2)
    assert "could not be completed" in agent.run("Find a time")
    assert active_pids() == before


@pytest.mark.parametrize("seconds", [0, -1, True, None, "1", float("nan"), float("inf")])
def test_invalid_deadlines_rejected(seconds):
    with pytest.raises(ValueError, match="timeout_seconds"):
        SchedulingAgent(FakeModel([]), Store.load(), timeout_seconds=seconds)
