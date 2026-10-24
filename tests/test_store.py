import json

import pytest

from scheduler.store import Store


@pytest.mark.parametrize("people,calendars", [
    ([{"id": "sam", "name": "Sam"}, {"id": "sam", "name": "Other"}], {}),
    ([{"id": "sam"}], {}),
    ([{"id": "sam", "name": "Sam"}], {"ghost": {}}),
    ([{"id": "sam", "name": "Sam"}], {"sam": {"bad": []}}),
    ([{"id": "sam", "name": "Sam"}], {"sam": {"2026-11-03": [{"start": "12:00", "end": "10:00"}]}}),
])
def test_invalid_fixtures_rejected(people, calendars):
    with pytest.raises(ValueError):
        Store(people, calendars)


def test_loads_supplied_data_directory(tmp_path):
    (tmp_path / "people.json").write_text(json.dumps([{"id": "sam", "name": "Sam"}]))
    (tmp_path / "calendars.json").write_text('{"sam": {}}')
    assert Store.load(tmp_path).people[0]["id"] == "sam"
