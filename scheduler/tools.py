"""Validated, read-only tools exposed to the model."""

from datetime import date as Date
from difflib import SequenceMatcher
import re
import unicodedata

from .slots import (
    DAY_START_MINUTES, DAY_END_MINUTES, SLOT_MINUTES, SLOTS_PER_DAY,
    availability_from_busy, combine_availability, find_free_windows,
    slot_to_time, time_to_minutes, time_to_slot, time_to_slot_ceil,
)
from .store import Store


def validate_date(date: str) -> None:
    if not isinstance(date, str):
        raise ValueError("Date must use YYYY-MM-DD.")
    try:
        parsed = Date.fromisoformat(date)
    except ValueError:
        raise ValueError("Date must use YYYY-MM-DD.") from None
    if parsed.isoformat() != date:
        raise ValueError("Date must use YYYY-MM-DD.")


NAME_SIMILARITY_THRESHOLD = 0.80
NAME_SIMILARITY_MARGIN = 0.10


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(re.sub(r"[^\w\s]", " ", "".join(
        c for c in value if not unicodedata.combining(c))).split())


def resolve_person(store: Store, person: str) -> str:
    """Resolve exact identities first, then conservative, unambiguous similarity."""
    if not isinstance(person, str) or not person.strip():
        raise ValueError("Attendees must be nonempty employee names or IDs.")
    query = normalize_name(person)
    exact = [p for p in store.people if query in
             (normalize_name(p["id"]), normalize_name(p["name"]))]
    if len(exact) == 1:
        return exact[0]["id"]
    if len(exact) > 1:
        raise ValueError(f"Ambiguous employee: {person}. Please use an employee ID.")
    ranked = []
    for p in store.people:
        full = normalize_name(p["name"])
        aliases = [normalize_name(p["id"]), full]
        if len(query.split()) == 1:
            aliases.extend(full.split())
        score = max(SequenceMatcher(None, query, alias).ratio() for alias in aliases)
        ranked.append((score, p))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked or ranked[0][0] < NAME_SIMILARITY_THRESHOLD:
        raise ValueError(f"Employee not found in the directory: {person}.")
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < NAME_SIMILARITY_MARGIN:
        candidates = ", ".join(p["name"] for score, p in ranked
                               if ranked[0][0] - score < NAME_SIMILARITY_MARGIN)
        raise ValueError(f"Ambiguous employee: {person}. Candidates: {candidates}. Please use an employee ID.")
    return ranked[0][1]["id"]


def list_people(store: Store) -> list[dict]:
    return store.people


def get_busy_times(store: Store, person: str, date: str) -> list[dict]:
    person = resolve_person(store, person)
    validate_date(date)
    return store.calendars.get(person, {}).get(date, [])


def find_free_slots(store: Store, attendees: list[str], date: str,
                    duration_minutes: int, earliest: str | None = None,
                    latest: str | None = None) -> list[dict]:
    if not isinstance(attendees, list) or not attendees:
        raise ValueError("Provide at least one attendee.")
    people = list(dict.fromkeys(resolve_person(store, p) for p in attendees))
    validate_date(date)
    if (type(duration_minutes) is not int or duration_minutes <= 0
            or duration_minutes % SLOT_MINUTES or duration_minutes > SLOTS_PER_DAY * SLOT_MINUTES):
        raise ValueError(f"Duration must be a positive multiple of {SLOT_MINUTES} minutes, at most one working day.")
    lower = DAY_START_MINUTES if earliest is None else time_to_minutes(earliest)
    upper = DAY_END_MINUTES if latest is None else time_to_minutes(latest)
    if not DAY_START_MINUTES <= lower < upper <= DAY_END_MINUTES:
        raise ValueError("Bounds must be ordered within working hours.")
    start = 0 if earliest is None else time_to_slot_ceil(earliest)
    end = SLOTS_PER_DAY if latest is None else time_to_slot(latest)
    if start > end:
        return []
    free = combine_availability([
        availability_from_busy(store.calendars.get(p, {}).get(date, [])) for p in people
    ])
    needed = duration_minutes // SLOT_MINUTES
    return [{"start": slot_to_time(s), "end": slot_to_time(s + needed)}
            for s in find_free_windows(free, needed, start, end)]


TOOLS = {"list_people": list_people, "get_busy_times": get_busy_times,
         "find_free_slots": find_free_slots}
