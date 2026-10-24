"""Deterministic availability on a fixed working-day grid."""

import re
from datetime import time

DAY_START = time(9, 0)
DAY_END = time(17, 0)
SLOT_MINUTES = 15
DAY_START_MINUTES = DAY_START.hour * 60 + DAY_START.minute
DAY_END_MINUTES = DAY_END.hour * 60 + DAY_END.minute
SLOTS_PER_DAY = (DAY_END_MINUTES - DAY_START_MINUTES) // SLOT_MINUTES


def time_to_minutes(clock: str) -> int:
    if not isinstance(clock, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", clock):
        raise ValueError("Times must use HH:MM (00:00–23:59).")
    hours, minutes = map(int, clock.split(":"))
    return hours * 60 + minutes


def minutes_to_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def time_to_slot(clock: str) -> int:
    return (time_to_minutes(clock) - DAY_START_MINUTES) // SLOT_MINUTES


def time_to_slot_ceil(clock: str) -> int:
    offset = time_to_minutes(clock) - DAY_START_MINUTES
    return -(-offset // SLOT_MINUTES)


def slot_to_time(index: int) -> str:
    return minutes_to_time(DAY_START_MINUTES + index * SLOT_MINUTES)


def availability_from_busy(busy_blocks: list[dict]) -> list[bool]:
    """Mark every slot with any overlap busy; clip blocks to working hours."""
    free = [True] * SLOTS_PER_DAY
    if not isinstance(busy_blocks, list):
        raise ValueError("Busy blocks must be a list.")
    for block in busy_blocks:
        if not isinstance(block, dict) or not {"start", "end"} <= block.keys():
            raise ValueError("Busy blocks require start and end times.")
        if time_to_minutes(block["start"]) >= time_to_minutes(block["end"]):
            raise ValueError("Busy blocks must end after they start.")
        start = max(0, time_to_slot(block["start"]))
        end = min(SLOTS_PER_DAY, time_to_slot_ceil(block["end"]))
        for i in range(start, end):
            free[i] = False
    return free


def validate_availability(free: list[bool]) -> None:
    if not isinstance(free, list) or len(free) != SLOTS_PER_DAY or any(type(x) is not bool for x in free):
        raise ValueError(f"Availability must contain {SLOTS_PER_DAY} booleans.")


def combine_availability(calendars: list[list[bool]]) -> list[bool]:
    combined = [True] * SLOTS_PER_DAY
    for free in calendars:
        validate_availability(free)
        combined = [a and b for a, b in zip(combined, free)]
    return combined


def find_free_windows(free: list[bool], slots_needed: int, start_slot: int = 0,
                      end_slot: int | None = None) -> list[int]:
    validate_availability(free)
    if type(slots_needed) is not int or not 1 <= slots_needed <= SLOTS_PER_DAY:
        raise ValueError("Meeting duration must fit within the working day.")
    if end_slot is None:
        end_slot = SLOTS_PER_DAY
    if (type(start_slot) is not int or type(end_slot) is not int
            or not 0 <= start_slot <= end_slot <= SLOTS_PER_DAY):
        raise ValueError("Search bounds must be ordered within the working day.")
    return [start for start in range(start_slot, end_slot - slots_needed + 1)
            if all(free[start:start + slots_needed])]
