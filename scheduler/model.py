"""Model interface plus a deterministic fake for tests and local development."""

import copy
import json
from typing import Protocol


class Model(Protocol):
    def complete(self, messages: list[dict]) -> str:
        """Given the conversation so far, return the model's raw text reply."""
        ...


class FakeModel:
    """A scripted model. Returns the responses in `script` in order.

    Each response is the raw text the "model" produces, so you can script
    malformed output as well as well-formed JSON. If `loop_last` is True,
    the final response is returned forever once the script runs out
    (useful for simulating a model that gets stuck).
    """

    def __init__(self, script: list[str], loop_last: bool = False):
        self.script = list(script)
        self.loop_last = loop_last
        self.calls: list[list[dict]] = []

    def complete(self, messages: list[dict]) -> str:
        self.calls.append(copy.deepcopy(messages))
        if not self.script:
            raise RuntimeError("FakeModel script exhausted")
        if self.loop_last and len(self.script) == 1:
            return self.script[0]
        return self.script.pop(0)


def tool_call(name: str, **args) -> str:
    """Helper to build a scripted tool-call response."""
    return json.dumps({"tool": name, "args": args})


def final(text: str) -> str:
    """Helper to build a scripted final answer."""
    return json.dumps({"final": text})


class InteractiveFakeModel(FakeModel):
    """Offline fake with a small scheduling grammar, not general language understanding.

    Unlike scripted FakeModel, responses are derived from the conversation.
    Successful tool arguments provide defaults for subsequent questions.
    """

    def __init__(self, today: str = "2026-11-02"):
        super().__init__([])
        self.today = today

    def complete(self, messages: list[dict]) -> str:
        import re
        from datetime import date, timedelta

        self.calls.append(copy.deepcopy(messages))
        if messages[-1]["role"] == "tool":
            return final("done")
        text = messages[-1]["content"].strip()
        if re.fullmatch(r"(?:list |show )?(?:people|employees|directory)[.!?]?", text, re.I):
            return tool_call("list_people")
        args = {}
        for index, message in enumerate(messages[:-1]):
            if message["role"] != "assistant":
                continue
            try:
                action = json.loads(message["content"])
            except (ValueError, TypeError):
                continue
            if (isinstance(action, dict) and action.get("tool") == "find_free_slots"
                    and index + 1 < len(messages) and messages[index + 1]["role"] == "tool"):
                args = dict(action["args"])
        # Extract names as written, including unknown names; resolution belongs to tools.
        recognized = False
        from .requests import attendee_names, requested_duration, requested_bounds
        names = attendee_names(text)
        if names:
            recognized = True
            args["attendees"] = names
        duration = requested_duration(text)
        if duration is not None:
            recognized = True
            args["duration_minutes"] = duration
        explicit_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
        weekday = re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text, re.I)
        today = date.fromisoformat(self.today)
        if explicit_date:
            recognized = True
            args["date"] = explicit_date.group()
        elif weekday:
            recognized = True
            day = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].index(weekday.group().lower())
            offset = (day - today.weekday()) % 7
            if re.search(r"\bnext\b", text, re.I) and offset == 0:
                offset = 7
            args["date"] = (today + timedelta(days=offset)).isoformat()
        elif re.search(r"\btomorrow\b", text, re.I):
            recognized = True
            args["date"] = (today + timedelta(days=1)).isoformat()
        elif re.search(r"\btoday\b", text, re.I):
            recognized = True
            args["date"] = self.today
        # New time constraints replace previous bounds; intersect all current bounds.
        bounds = requested_bounds(text)
        if bounds is not None:
            recognized = True
            args.pop("earliest", None)
            args.pop("latest", None)
            args.update(bounds)
        if re.search(r"\bat\b", text, re.I):
            return final("clarification needed")
        if not recognized or not {"attendees", "date", "duration_minutes"} <= args.keys():
            return final("clarification needed")
        return tool_call("find_free_slots", **args)
