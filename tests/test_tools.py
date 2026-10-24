import pytest

from scheduler.store import Store
from scheduler.tools import find_free_slots, get_busy_times, list_people


def search(**overrides):
    args = dict(attendees=["priya", "sam"], date="2026-11-03", duration_minutes=30)
    args.update(overrides)
    return find_free_slots(Store.load(), **args)


def test_directory_and_busy_lookup():
    store = Store.load()
    assert list_people(store) == store.people
    assert get_busy_times(store, "Sam Okafor", "2026-11-04") == [
        {"start": "09:00", "end": "09:30", "title": "Standup"}]


def test_afternoon_exact_results_include_final_window():
    assert search(earliest="13:00") == [
        {"start": "13:00", "end": "13:30"},
        {"start": "13:15", "end": "13:45"},
        {"start": "13:30", "end": "14:00"},
        {"start": "15:00", "end": "15:30"},
        {"start": "16:00", "end": "16:30"},
        {"start": "16:15", "end": "16:45"},
        {"start": "16:30", "end": "17:00"},
    ]


def test_45_minute_meetings_are_exact():
    assert search(duration_minutes=45, earliest="13:00", latest="14:00") == [
        {"start": "13:00", "end": "13:45"},
        {"start": "13:15", "end": "14:00"},
    ]


def test_non_aligned_bounds_round_inward():
    assert search(earliest="13:01", latest="13:59") == [
        {"start": "13:15", "end": "13:45"}]
    assert search(earliest="13:01", latest="13:14") == []


def test_hour_long_and_full_day():
    assert search(duration_minutes=60, earliest="13:00", latest="14:00") == [
        {"start": "13:00", "end": "14:00"}]
    assert search(attendees=["mei"], date="2026-11-04", duration_minutes=480) == [
        {"start": "09:00", "end": "17:00"}]
    assert search(earliest="14:00", latest="15:00") == []


@pytest.mark.parametrize("overrides", [
    {"attendees": []}, {"attendees": "sam"}, {"attendees": ["ghost"]},
    {"attendees": ["priya", "ghost"]}, {"attendees": [None]},
    {"duration_minutes": 0}, {"duration_minutes": -15}, {"duration_minutes": 20},
    {"duration_minutes": True}, {"duration_minutes": 15.0}, {"duration_minutes": 495},
    {"date": "2026-02-30"}, {"date": "20261103"}, {"date": None},
    {"earliest": "08:00"}, {"latest": "18:00"}, {"latest": "bad"},
    {"earliest": "14:00", "latest": "13:00"},
])
def test_bad_arguments_rejected(overrides):
    with pytest.raises(ValueError):
        search(**overrides)


def test_unknown_busy_lookup_is_not_empty_calendar():
    with pytest.raises(ValueError, match="ghost"):
        get_busy_times(Store.load(), "ghost", "2026-11-03")
    assert get_busy_times(Store.load(), "sam", "2026-11-02")
    assert get_busy_times(Store.load(), "sam", "2026-11-05") == []


@pytest.mark.parametrize("name,expected", [
    ("Priyaa", "priya"), ("Samm", "sam"), ("Priya Rman", "priya"),
    ("  PRIYA   RAMAN ", "priya"), ("Okafor", "sam"),
])
def test_fuzzy_person_resolution(name, expected):
    from scheduler.tools import resolve_person
    assert resolve_person(Store.load(), name) == expected


def test_fuzzy_rejects_ambiguous_and_low_confidence_names():
    from scheduler.tools import resolve_person
    store = Store([{"id": "ann1", "name": "Anna Smith"},
                   {"id": "ann2", "name": "Anne Smith"}], {})
    with pytest.raises(ValueError, match="Ambiguous"):
        resolve_person(store, "Anny Smith")
    with pytest.raises(ValueError, match="Ambiguous"):
        resolve_person(store, "Smith")
    with pytest.raises(ValueError, match="not found"):
        resolve_person(store, "Zzzzz")
    assert resolve_person(store, "ann1") == "ann1"
