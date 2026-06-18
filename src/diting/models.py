# src/diting/models.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class SignalItem:
    source: str
    text: str
    mtime: float

@dataclass(frozen=True)
class Interests:
    topics: tuple[str, ...]
    entities: tuple[str, ...]
    open_loops: tuple[str, ...]
    decisions: tuple[str, ...]

@dataclass(frozen=True)
class Candidate:
    title: str
    url: str
    summary: str
    source: str
    body: str = ""

@dataclass(frozen=True)
class RankedItem:
    title: str
    url: str
    one_liner: str
    why_it_matters: str
    source: str
    lens: str

@dataclass(frozen=True)
class Report:
    lens: str
    date: str
    items: tuple[RankedItem, ...]
    notes: tuple[str, ...]

    def is_empty(self) -> bool:
        return len(self.items) == 0
