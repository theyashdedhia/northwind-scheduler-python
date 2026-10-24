"""Loads the people directory and calendars from JSON files."""

import json
from datetime import date as Date
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class Store:
    people: list[dict]
    calendars: dict[str, dict[str, list[dict]]]

    def __post_init__(self) -> None:
        from .slots import availability_from_busy

        if not isinstance(self.people, list) or not isinstance(self.calendars, dict):
            raise ValueError("Directory and calendars have invalid shapes.")
        ids = set()
        for person in self.people:
            if (not isinstance(person, dict)
                    or not isinstance(person.get("id"), str) or not person["id"].strip()
                    or not isinstance(person.get("name"), str) or not person["name"].strip()
                    or person["id"].casefold() in ids):
                raise ValueError("Employees require unique IDs and nonempty names.")
            ids.add(person["id"].casefold())
        for person, dates in self.calendars.items():
            if person not in {p["id"] for p in self.people} or not isinstance(dates, dict):
                raise ValueError("Calendars must belong to directory employees.")
            for date, blocks in dates.items():
                if not isinstance(date, str) or Date.fromisoformat(date).isoformat() != date:
                    raise ValueError("Calendar dates must use YYYY-MM-DD.")
                availability_from_busy(blocks)

    @classmethod
    def load(cls, data_dir: Path = DATA_DIR) -> "Store":
        with open(data_dir / "people.json") as f:
            people = json.load(f)
        with open(data_dir / "calendars.json") as f:
            calendars = json.load(f)
        return cls(people=people, calendars=calendars)
