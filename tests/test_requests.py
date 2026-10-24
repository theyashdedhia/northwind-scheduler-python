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
