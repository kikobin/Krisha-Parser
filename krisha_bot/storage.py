from __future__ import annotations

import datetime
import json
import sqlite3
from typing import List, Optional


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_listings (
                listing_id TEXT PRIMARY KEY,
                seen_at    TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_seen_at ON seen_listings(seen_at)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                listing_id TEXT PRIMARY KEY,
                chat_id    INTEGER NOT NULL,
                added_at   TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                chat_id  INTEGER PRIMARY KEY,
                settings TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id    INTEGER NOT NULL,
                listing_id TEXT NOT NULL,
                listing    TEXT NOT NULL,
                sent_at    TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_chat ON history(chat_id, sent_at)"
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Seen listings
    # ------------------------------------------------------------------

    def is_seen(self, listing_id: str) -> bool:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM seen_listings WHERE listing_id = ?", (listing_id,)
        ).fetchone()
        conn.close()
        return row is not None

    def mark_seen(self, listing_id: str):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO seen_listings (listing_id, seen_at) VALUES (?, ?)",
            (listing_id, datetime.datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def bulk_mark_seen(self, ids: List[str]):
        now = datetime.datetime.now().isoformat()
        conn = self._get_conn()
        conn.executemany(
            "INSERT OR IGNORE INTO seen_listings (listing_id, seen_at) VALUES (?, ?)",
            [(id_, now) for id_ in ids],
        )
        conn.commit()
        conn.close()

    def filter_new(self, listings: list) -> list:
        return [l for l in listings if not self.is_seen(l["id"]) and not self.is_blacklisted(l["id"])]

    def seen_count(self) -> int:
        conn = self._get_conn()
        count = conn.execute("SELECT COUNT(*) FROM seen_listings").fetchone()[0]
        conn.close()
        return count

    def prune(self, max_age_days: int = 30):
        cutoff = (
            datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        ).isoformat()
        conn = self._get_conn()
        conn.execute("DELETE FROM seen_listings WHERE seen_at < ?", (cutoff,))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Blacklist
    # ------------------------------------------------------------------

    def blacklist(self, listing_id: str, chat_id: int):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO blacklist (listing_id, chat_id, added_at) VALUES (?, ?, ?)",
            (listing_id, chat_id, datetime.datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def is_blacklisted(self, listing_id: str) -> bool:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM blacklist WHERE listing_id = ?", (listing_id,)
        ).fetchone()
        conn.close()
        return row is not None

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def save_to_history(self, chat_id: int, listing: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO history (chat_id, listing_id, listing, sent_at) VALUES (?, ?, ?, ?)",
            (chat_id, listing["id"], json.dumps(listing, ensure_ascii=False),
             datetime.datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def get_history(self, chat_id: int, limit: int = 5) -> list:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT listing FROM history WHERE chat_id = ? ORDER BY sent_at DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        conn.close()
        return [json.loads(r["listing"]) for r in rows]

    def get_stats(self, chat_id: int) -> dict:
        conn = self._get_conn()
        today = datetime.date.today().isoformat()
        total = conn.execute(
            "SELECT COUNT(*) FROM history WHERE chat_id = ?", (chat_id,)
        ).fetchone()[0]
        today_count = conn.execute(
            "SELECT COUNT(*) FROM history WHERE chat_id = ? AND sent_at >= ?",
            (chat_id, today),
        ).fetchone()[0]
        blacklisted = conn.execute(
            "SELECT COUNT(*) FROM blacklist WHERE chat_id = ?", (chat_id,)
        ).fetchone()[0]
        conn.close()
        return {"total": total, "today": today_count, "blacklisted": blacklisted}

    # ------------------------------------------------------------------
    # User settings
    # ------------------------------------------------------------------

    def get_settings(self, chat_id: int) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT settings FROM user_settings WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        conn.close()
        return json.loads(row["settings"]) if row else None

    def save_settings(self, chat_id: int, settings: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO user_settings (chat_id, settings) VALUES (?, ?)",
            (chat_id, json.dumps(settings, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    def update_settings(self, chat_id: int, updates: dict):
        existing = self.get_settings(chat_id) or {}
        existing.update(updates)
        self.save_settings(chat_id, existing)

    def get_active_chats(self) -> List[int]:
        conn = self._get_conn()
        rows = conn.execute("SELECT chat_id, settings FROM user_settings").fetchall()
        conn.close()
        return [
            row["chat_id"]
            for row in rows
            if json.loads(row["settings"]).get("active", False)
        ]
