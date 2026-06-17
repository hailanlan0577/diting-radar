# src/diting/state.py
from __future__ import annotations
import os, sqlite3
import yaml

_DEFAULT_PROFILE = {"stack": [], "tools": [], "topics": []}

class StateStore:
    def __init__(self, state_dir: str):
        self.dir = state_dir
        os.makedirs(self.dir, exist_ok=True)
        self._db = os.path.join(self.dir, "pushed.db")
        self._profile = os.path.join(self.dir, "interest_profile.yaml")
        with sqlite3.connect(self._db) as c:
            c.execute("CREATE TABLE IF NOT EXISTS pushed (url TEXT PRIMARY KEY, title TEXT)")

    def is_pushed(self, url: str) -> bool:
        with sqlite3.connect(self._db) as c:
            return c.execute("SELECT 1 FROM pushed WHERE url=?", (url,)).fetchone() is not None

    def mark_pushed(self, url: str, title: str) -> None:
        with sqlite3.connect(self._db) as c:
            c.execute("INSERT OR IGNORE INTO pushed (url, title) VALUES (?, ?)", (url, title))

    def load_profile(self) -> dict:
        if not os.path.exists(self._profile):
            return dict(_DEFAULT_PROFILE)
        with open(self._profile, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or dict(_DEFAULT_PROFILE)

    def save_profile(self, profile: dict) -> None:
        with open(self._profile, "w", encoding="utf-8") as f:
            yaml.safe_dump(profile, f, allow_unicode=True)
