# src/diting/state.py
from __future__ import annotations
import json
import os
import sqlite3
import yaml

_DEFAULT_PROFILE = {"stack": [], "tools": [], "topics": [], "repos": []}

class StateStore:
    def __init__(self, state_dir: str):
        self.dir = state_dir
        os.makedirs(self.dir, exist_ok=True)
        self._db = os.path.join(self.dir, "pushed.db")
        self._profile = os.path.join(self.dir, "interest_profile.yaml")
        self._versions = os.path.join(self.dir, "versions.json")
        self._dug = os.path.join(self.dir, "dug_topics.json")
        self._proj = os.path.join(self.dir, "project_radar.json")
        with sqlite3.connect(self._db) as c:
            c.execute("CREATE TABLE IF NOT EXISTS pushed (url TEXT PRIMARY KEY, title TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS project_pushed "
                      "(slug TEXT, url TEXT, PRIMARY KEY (slug, url))")

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

    def _load_versions(self) -> dict[str, str]:
        if not os.path.exists(self._versions):
            return {}
        try:
            with open(self._versions, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_versions(self, data: dict[str, str]) -> None:
        try:
            with open(self._versions, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError as e:
            print(f"[谛听] 写 versions.json 失败（本次版本快照未保存）：{e}")

    def get_seen_version(self, repo: str) -> str | None:
        return self._load_versions().get(repo)

    def set_seen_version(self, repo: str, version: str) -> None:
        data = self._load_versions()
        self._save_versions({**data, repo: version})

    def _load_dug(self) -> list[str]:
        if not os.path.exists(self._dug):
            return []
        try:
            with open(self._dug, "r", encoding="utf-8") as f:
                return json.load(f) or []
        except (json.JSONDecodeError, OSError):
            return []

    def is_dug(self, topic: str) -> bool:
        return topic in self._load_dug()

    def mark_dug(self, topic: str) -> None:
        dug = self._load_dug()
        if topic not in dug:
            dug.append(topic)
        try:
            with open(self._dug, "w", encoding="utf-8") as f:
                json.dump(dug, f, ensure_ascii=False)
        except OSError as e:
            print(f"[谛听] 写 dug_topics.json 失败：{e}")

    def is_project_pushed(self, slug: str, url: str) -> bool:
        with sqlite3.connect(self._db) as c:
            return c.execute("SELECT 1 FROM project_pushed WHERE slug=? AND url=?",
                             (slug, url)).fetchone() is not None

    def mark_project_pushed(self, slug: str, url: str) -> None:
        with sqlite3.connect(self._db) as c:
            c.execute("INSERT OR IGNORE INTO project_pushed (slug, url) VALUES (?, ?)",
                      (slug, url))

    def _load_proj_hashes(self) -> dict[str, str]:
        if not os.path.exists(self._proj):
            return {}
        try:
            with open(self._proj, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except (json.JSONDecodeError, OSError):
            return {}

    def get_status_hash(self, slug: str) -> str | None:
        return self._load_proj_hashes().get(slug)

    def set_status_hash(self, slug: str, h: str) -> None:
        data = self._load_proj_hashes()
        data[slug] = h
        try:
            with open(self._proj, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError as e:
            print(f"[谛听] 写 project_radar.json 失败：{e}")
