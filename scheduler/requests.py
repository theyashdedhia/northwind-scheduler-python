"""Deterministic attendee checks independent of model-generated tool arguments."""

import re

from .store import Store
from .tools import normalize_name, resolve_person


NON_PERSON = (r"^(?:later|earlier|afternoon|morning|noon|after|before|from|between|"
              r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow|next|\d+)\b")


def attendee_names(text: str) -> list[str]:
    """Read explicit attendee clauses, retaining unknown and misspelled names."""
    names = re.search(
        r"\b(?:with|for|check|about)\s+(.+?)(?=\s+(?:on|at|after|before|from|between|next|today|tomorrow|this|in the)\b|\s+\d|$)",
        text, re.I)
    if not names:
        return []
    fragment = re.sub(r"[?.!]+$", "", names.group(1)).strip()
    if re.match(NON_PERSON, fragment, re.I):
        return []
    return [p.strip() for p in re.split(r"\s+and\s+|\s*&\s*|,", fragment, flags=re.I)]


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
