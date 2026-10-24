import pytest

from scheduler.requests import attendee_names


@pytest.mark.parametrize("text,expected", [
    ("Find 30 minutes with Sam on Tuesday and with Ghost", ["Sam", "Ghost"]),
    ("Find 30 minutes with Sam and with Ghost on Tuesday", ["Sam", "Ghost"]),
    ("Check Sam; check Mei on Tuesday", ["Sam", "Mei"]),
    ("What about after 16:00?", []),
    ("Check Sam on Tuesday. What about Ghost?", ["Sam", "Ghost"]),
    ("Find 30 minutes for Sam & Mei, Luis on Tuesday", ["Sam", "Mei", "Luis"]),
])
def test_all_attendee_clauses_are_extracted(text, expected):
    assert attendee_names(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("Sam and Ghost need 30 minutes on Tuesday", ["Sam", "Ghost"]),
    ("Sam, Mei & Luis want an hour tomorrow", ["Sam", "Mei", "Luis"]),
    ("Check Sam on Tuesday. Mei and Ghost need 30 minutes", ["Sam", "Mei", "Ghost"]),
])
def test_subject_first_attendees_include_unknown_names(text, expected):
    assert attendee_names(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("Find 30 minutes", 30), ("Find an hour", 60), ("Find 1.5 hours", 90),
    ("Find .5 hours", 30), ("Try 30.0 minutes", 30), ("Find 45mins", 45),
    ("Find a time", None),
])
def test_complete_numeric_durations(text, expected):
    from scheduler.requests import requested_duration
    assert requested_duration(text) == expected


@pytest.mark.parametrize("text", [
    "Find -30 minutes", "Find 30.15 minutes", "Find 1.25 minutes", "Find 0 hours",
    "Find 30 minutes and 45 minutes", "Find thirty minutes", "Find 1e2 minutes",
    "Find 1.2.3 hours", "Find 29.999999999999999999999999999999 minutes",
])
def test_invalid_durations_are_not_reinterpreted(text):
    from scheduler.requests import requested_duration
    with pytest.raises(ValueError):
        requested_duration(text)


@pytest.mark.parametrize("text,expected", [
    ("after 12:00 and after 16:00", {"earliest": "16:00"}),
    ("after 16:00 and after 12:00", {"earliest": "16:00"}),
    ("before 14:00 and before 13:00", {"latest": "13:00"}),
    ("morning before 10:00", {"latest": "10:00"}),
    ("afternoon after 16:00", {"earliest": "16:00"}),
    ("between 09:00 and 17:00 and between 13:00 and 16:00", {"earliest": "13:00", "latest": "16:00"}),
])
def test_all_time_bounds_intersect(text, expected):
    from scheduler.requests import requested_bounds
    assert requested_bounds(text) == expected
