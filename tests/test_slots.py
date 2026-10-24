import pytest

from scheduler.slots import (
    SLOTS_PER_DAY, availability_from_busy, combine_availability,
    find_free_windows, slot_to_time, time_to_slot, time_to_minutes,
)


def test_slot_time_conversions():
    assert slot_to_time(0) == "09:00"
    assert slot_to_time(3) == "09:45"
    assert slot_to_time(SLOTS_PER_DAY) == "17:00"
    assert time_to_slot("10:50") == 7


def test_partial_overlap_and_clipping():
    free = availability_from_busy([
        {"start": "10:00", "end": "10:40"},
        {"start": "08:00", "end": "09:10"},
        {"start": "16:50", "end": "18:00"},
    ])
    assert free[0] is False
    assert free[4:8] == [False, False, False, True]
    assert free[-1] is False


def test_combine_availability():
    a, b = [True] * SLOTS_PER_DAY, [True] * SLOTS_PER_DAY
    a[2] = b[1] = False
    assert combine_availability([a, b]) == [True, False, False] + [True] * (SLOTS_PER_DAY - 3)
    with pytest.raises(ValueError):
        combine_availability([a, [True]])


def test_windows_include_last_start_and_full_day():
    free = [True] * SLOTS_PER_DAY
    assert find_free_windows(free, 1) == list(range(SLOTS_PER_DAY))
    assert find_free_windows(free, SLOTS_PER_DAY) == [0]
    assert find_free_windows(free, 2, 3, 5) == [3]
    assert find_free_windows([False] * SLOTS_PER_DAY, 1) == []


def test_overlapping_windows():
    free = [False, True, True, True] + [False] * (SLOTS_PER_DAY - 4)
    assert find_free_windows(free, 2) == [1, 2]


@pytest.mark.parametrize("duration", [0, -1, True, 1.5, SLOTS_PER_DAY + 1])
def test_invalid_window_duration(duration):
    with pytest.raises(ValueError):
        find_free_windows([True] * SLOTS_PER_DAY, duration)


@pytest.mark.parametrize("clock", ["9:00", "24:00", "12:60", "bad", 900, None])
def test_invalid_clock(clock):
    with pytest.raises(ValueError):
        time_to_minutes(clock)


@pytest.mark.parametrize("block", [{"start": "11:00", "end": "10:00"}, {}, {"start": "bad", "end": "12:00"}])
def test_invalid_busy_block(block):
    with pytest.raises(ValueError):
        availability_from_busy([block])


@pytest.mark.parametrize("start,end", [(-1, 4), (0, SLOTS_PER_DAY + 1), (5, 4)])
def test_invalid_window_bounds(start, end):
    with pytest.raises(ValueError):
        find_free_windows([True] * SLOTS_PER_DAY, 1, start, end)
