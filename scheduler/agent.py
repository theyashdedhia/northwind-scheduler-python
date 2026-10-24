"""Bounded tool orchestration with per-session conversation history."""

import json
import math

from .execution import execute_request, RequestDeadlineExceeded

from .model import Model
from .prompts import build_system_prompt
from .requests import requested_attendees
from .store import Store
from .tools import TOOLS, resolve_person


def unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject ambiguous objects, including nested tool argument objects."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}.")
        result[key] = value
    return result


class SchedulingAgent:
    def __init__(self, model: Model, store: Store, today: str = "2026-11-02",
                 max_steps: int = 8, timeout_seconds: float = 30):
        if type(max_steps) is not int or max_steps < 1:
            raise ValueError("max_steps must be a positive integer.")
        if (type(timeout_seconds) not in (int, float)
                or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError("timeout_seconds must be a positive finite number.")
        self.timeout_seconds = timeout_seconds
        self.model = model
        self.store = store
        self.today = today
        self.max_steps = max_steps
        self.turns: list[list[dict]] = []
        self.attendees: list[str] = []

    def reset(self) -> None:
        """Start a new conversation without retaining previous requests."""
        self.turns.clear()
        self.attendees.clear()

    def run(self, user_request: str) -> str:
        """Run one turn within the deadline; publish session state only on completion."""
        if not isinstance(user_request, str) or not user_request.strip():
            return "Please enter a scheduling question."
        try:
            answer, turns, attendees, fake_state = execute_request(self, user_request)
        except RequestDeadlineExceeded:
            answer = "The request timed out. Please try a more specific question."
        except Exception:
            answer = "The request could not be completed. Please try again."
        else:
            self.turns, self.attendees = turns, attendees
            if fake_state is not None:
                self.model.script, self.model.calls = fake_state
            return answer
        # Partial work from a cancelled/failed worker never changes session state.
        self.turns.append([{"role": "user", "content": user_request},
                           {"role": "assistant", "content": answer}])
        self.turns = self.turns[-10:]
        return answer

    def _run(self, user_request: str) -> str:
        """Execute inside the disposable worker; retain ten completed turns."""
        if not isinstance(user_request, str) or not user_request.strip():
            return "Please enter a scheduling question."
        turn = [{"role": "user", "content": user_request}]
        messages = [{"role": "system", "content": build_system_prompt(self.store.people, self.today)}]
        for previous in self.turns:
            messages.extend(previous)
        messages.extend(turn)

        def finish(answer: str) -> str:
            turn.append({"role": "assistant", "content": answer})
            self.turns.append(turn)
            self.turns = self.turns[-10:]
            return answer

        # Resolve every explicit request name before any model action can bypass it.
        try:
            expected = requested_attendees(self.store, user_request, self.attendees)
        except ValueError as error:
            return finish(f"Unable to complete the request: {error}")

        # Only current-turn tool results may substantiate an answer.
        verified_answer = None
        for _ in range(self.max_steps):
            try:
                raw = self.model.complete(messages)
            except Exception:
                return finish("The model is unavailable. Please try again.")
            try:
                action = json.loads(raw, object_pairs_hook=unique_json_object)
                if not isinstance(action, dict):
                    raise ValueError("Expected a JSON object.")
                if set(action) == {"final"}:
                    if not isinstance(action["final"], str) or not action["final"].strip():
                        raise ValueError("Final must be nonempty text.")
                    # Never publish unverified model-authored meeting claims.
                    return finish(verified_answer or
                                  "Please provide attendee IDs or full names, a date, and a duration; no availability has been verified.")
                if set(action) != {"tool", "args"}:
                    raise ValueError("Use either final or tool and args.")
                if not isinstance(action["tool"], str) or action["tool"] not in TOOLS:
                    raise ValueError("Unknown tool.")
                if not isinstance(action["args"], dict):
                    raise ValueError("Tool arguments must be an object.")
                name, args = action["tool"], action["args"]
                if name == "find_free_slots":
                    supplied = args.get("attendees")
                    if not isinstance(supplied, list) or not supplied:
                        raise ValueError("Provide at least one attendee.")
                    actual = {resolve_person(self.store, p) for p in supplied}
                    if expected and actual != expected:
                        raise ValueError("Tool attendees do not match the request. Please restate the complete attendee list.")
                result = TOOLS[name](self.store, **args)
            except (ValueError, TypeError, KeyError) as error:
                return finish(f"Unable to complete the request: {error}")

            exchange = [{"role": "assistant", "content": raw},
                        {"role": "tool", "content": json.dumps(result)}]
            messages.extend(exchange)
            turn.extend(exchange)
            if name == "find_free_slots":
                ids = list(dict.fromkeys(resolve_person(self.store, p) for p in args["attendees"]))
                self.attendees = ids
                names = ", ".join(next(p["name"] for p in self.store.people if p["id"] == pid) for pid in ids)
                windows = ", ".join(f"{s['start']}–{s['end']}" for s in result)
                verified_answer = (f"Availability for {names} on {args['date']} "
                                   f"({args['duration_minutes']} minutes): {windows}." if result else
                                   f"No shared availability for {names} on {args['date']} within the requested bounds.")
            elif name == "list_people":
                verified_answer = "Employees: " + ", ".join(f"{p['name']} ({p['id']})" for p in result) + "."
            else:
                windows = ", ".join(f"{b['start']}–{b['end']}" for b in result)
                verified_answer = f"Busy times for {args['person']} on {args['date']}: {windows or 'none recorded'}."
        return finish("The request exceeded the tool-call limit. Please try a more specific question.")
