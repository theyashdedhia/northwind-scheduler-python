"""Deterministic attendee checks independent of model-generated tool arguments."""

import re
from decimal import Decimal, InvalidOperation, localcontext

from .slots import (
    DAY_START_MINUTES, DAY_END_MINUTES, SLOT_MINUTES, SLOTS_PER_DAY,
    minutes_to_time, time_to_minutes,
)
from .store import Store
from .tools import normalize_name, resolve_person


NON_PERSON = (r"^(?:later|earlier|afternoon|morning|noon|after|before|from|between|"
              r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow|next|\d+)\b")


def attendee_names(text: str) -> list[str]:
    """Read explicit attendee clauses, retaining unknown and misspelled names."""
    names = []
    clauses = re.finditer(
        r"\b(?:with|for|check|about)\s+(.+?)(?="
        r"\s+(?:and\s+)?(?:with|for|check|about)\s+|"
        r"\s+(?:on|at|after|before|from|between|next|today|tomorrow|this|in the)\b|"
        r"\s+\d|[;.!?]|$)", text, re.I)
    for clause in clauses:
        fragment = clause.group(1).strip()
        if re.match(NON_PERSON, fragment, re.I):
            continue
        names.extend(p.strip() for p in re.split(r"\s+and\s+|\s*&\s*|,", fragment, flags=re.I))
    # Also read subject-first requests, retaining unknown names alongside known ones.
    subjects = re.finditer(
        r"(?:^|[;.!?]\s*)([^;.!?]+?)\s+(?:need|needs|want|wants|require|requires)\b",
        text, re.I)
    for subject in subjects:
        fragment = subject.group(1).strip()
        # Pronouns are not directory names; ask for a named group instead of guessing.
        if re.fullmatch(r"I|we|they|he|she|you", fragment, re.I):
            raise ValueError("Please specify the complete attendee list using employee names.")
        names.extend(p.strip() for p in re.split(r"\s+and\s+|\s*&\s*|,", fragment, flags=re.I))
    return names


def requested_duration(text: str) -> int | None:
    """Read complete numeric tokens; never reinterpret signs or decimal suffixes."""
    values = []
    for match in re.finditer(r"(?<!\w)([^\s]+?)\s*(minutes?|mins?|hours?|hrs?)\b", text, re.I):
        token, unit = match.groups()
        if token.casefold() in {"a", "an", "one"}:
            token = "1"
        if len(token) > 100 or not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)", token):
            raise ValueError("Use a positive numeric duration in minutes or hours.")
        try:
            with localcontext() as context:
                context.prec = len(token) + 10
                minutes = Decimal(token) * (60 if unit.lower().startswith("h") else 1)
                if (minutes <= 0 or minutes > SLOTS_PER_DAY * SLOT_MINUTES
                        or minutes != minutes.to_integral_value() or minutes % SLOT_MINUTES):
                    raise ValueError(f"Duration must be a positive multiple of {SLOT_MINUTES} minutes, at most one working day.")
        except InvalidOperation:
            raise ValueError("Invalid meeting duration.") from None
        values.append(int(minutes))
    if len(set(values)) > 1:
        raise ValueError("Please specify one meeting duration.")
    return values[0] if values else None


def requested_bounds(text: str) -> dict[str, str] | None:
    """Intersect every explicit bound and day period in this request."""
    lower, upper = [], []

    def clock(value: str) -> int:
        value = value.rstrip("?.!,;")
        return time_to_minutes("12:00" if value.casefold() == "noon" else value)

    for match in re.finditer(r"\b(after|before|from|to)\s+(\S+)", text, re.I):
        word, value = match.groups()
        (lower if word.lower() in {"after", "from"} else upper).append(clock(value))
    between = list(re.finditer(r"\bbetween\s+(\S+)\s+and\s+(\S+)", text, re.I))
    if len(between) != len(re.findall(r"\bbetween\b", text, re.I)):
        raise ValueError("Use 'between HH:MM and HH:MM' for time bounds.")
    for match in between:
        lower.append(clock(match.group(1)))
        upper.append(clock(match.group(2)))
    if re.search(r"\bafternoon\b", text, re.I):
        lower.append(12 * 60)
    if re.search(r"\bmorning\b", text, re.I):
        upper.append(12 * 60)
    if not lower and not upper:
        return None
    if any(not DAY_START_MINUTES <= value <= DAY_END_MINUTES for value in lower + upper):
        raise ValueError("Bounds must be within working hours.")
    start, end = max(lower, default=DAY_START_MINUTES), min(upper, default=DAY_END_MINUTES)
    if start >= end:
        raise ValueError("Bounds must be ordered within working hours.")
    return {**({"earliest": minutes_to_time(start)} if lower else {}),
            **({"latest": minutes_to_time(end)} if upper else {})}


def requested_attendees(store: Store, text: str, previous: list[str]) -> set[str]:
    """Resolve user mentions, never deriving expected attendees from the model.

    Explicit lists replace the previous group. Time-only follow-ups retain it.
    Unsupported additive/negative attendee edits require a complete replacement.
    """
    if re.search(r"\b(add|include|remove|exclude|without|except|instead of)\b", text, re.I):
        raise ValueError("Please restate the complete attendee list using 'with NAME and NAME'.")
    names = attendee_names(text)
    expected = {resolve_person(store, name) for name in names}
    normalized = normalize_name(text)
    # Also detect known people mentioned outside the demo's attendee-clause grammar.
    for person in store.people:
        aliases = {normalize_name(person['id']), normalize_name(person['name'])}
        if any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", normalized)
               for alias in aliases):
            expected.add(person['id'])
    return expected or set(previous)
