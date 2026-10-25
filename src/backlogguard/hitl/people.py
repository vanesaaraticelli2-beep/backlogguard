"""Personas que pueden decidir (config/people.yaml). Fuera del curso: no hay autenticación real."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Person(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2)
    display: str
    role: str


class PeopleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    people: list[Person]

    def get(self, name: str) -> Person | None:
        return next((person for person in self.people if person.name == name), None)

    def with_role(self, role: str) -> list[Person]:
        return [person for person in self.people if person.role == role]


def load_people(path: str | Path) -> PeopleConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        return PeopleConfig.model_validate(yaml.safe_load(handle))
