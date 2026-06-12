"""Tests for SQLite storage — seen IDs and user settings."""

import pytest
import tempfile
import os
from tests.fixtures import SAMPLE_LISTING


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_krisha.db")


class TestSeenStorage:
    """Tests for tracking which listing IDs have already been sent."""

    def test_new_db_has_no_seen_ids(self, db_path):
        from krisha_bot.storage import Storage
        s = Storage(db_path)
        assert s.is_seen("101234567") is False

    def test_mark_seen_persists(self, db_path):
        from krisha_bot.storage import Storage
        s = Storage(db_path)
        s.mark_seen("101234567")
        assert s.is_seen("101234567") is True

    def test_mark_seen_survives_reopen(self, db_path):
        """Seen IDs persist across Storage instance restarts."""
        from krisha_bot.storage import Storage
        s = Storage(db_path)
        s.mark_seen("101234567")
        s2 = Storage(db_path)
        assert s2.is_seen("101234567") is True

    def test_unseen_id_not_affected_by_other_marks(self, db_path):
        from krisha_bot.storage import Storage
        s = Storage(db_path)
        s.mark_seen("111111")
        assert s.is_seen("222222") is False

    def test_filter_new_listings_returns_only_unseen(self, db_path):
        """filter_new() removes already-seen listings from a list."""
        from krisha_bot.storage import Storage
        from tests.fixtures import SAMPLE_LISTING_2
        s = Storage(db_path)
        s.mark_seen(SAMPLE_LISTING["id"])
        listings = [SAMPLE_LISTING, SAMPLE_LISTING_2]
        new = s.filter_new(listings)
        assert len(new) == 1
        assert new[0]["id"] == SAMPLE_LISTING_2["id"]

    def test_filter_new_empty_list(self, db_path):
        from krisha_bot.storage import Storage
        s = Storage(db_path)
        assert s.filter_new([]) == []

    def test_bulk_mark_seen(self, db_path):
        from krisha_bot.storage import Storage
        s = Storage(db_path)
        ids = ["aaa", "bbb", "ccc"]
        s.bulk_mark_seen(ids)
        for id_ in ids:
            assert s.is_seen(id_) is True

    def test_seen_count(self, db_path):
        from krisha_bot.storage import Storage
        s = Storage(db_path)
        s.mark_seen("x1")
        s.mark_seen("x2")
        assert s.seen_count() == 2

    def test_old_entries_are_pruned(self, db_path):
        """Entries older than max_age days are removed to keep DB small."""
        from krisha_bot.storage import Storage
        import datetime
        s = Storage(db_path)
        s.mark_seen("old_id")
        # Manually backdate the entry
        conn = s._get_conn()
        old_date = (datetime.datetime.now() - datetime.timedelta(days=31)).isoformat()
        conn.execute("UPDATE seen_listings SET seen_at = ? WHERE listing_id = 'old_id'", (old_date,))
        conn.commit()
        s.prune(max_age_days=30)
        assert s.is_seen("old_id") is False


class TestSettingsStorage:
    """Tests for persisting user filter settings."""

    def test_default_settings_are_empty(self, db_path):
        from krisha_bot.storage import Storage
        s = Storage(db_path)
        settings = s.get_settings(chat_id=123456)
        assert settings is None

    def test_save_and_load_settings(self, db_path):
        from krisha_bot.storage import Storage
        s = Storage(db_path)
        data = {"price_from": 50000, "rooms": [1, 2], "polygon_url": "https://..."}
        s.save_settings(chat_id=123456, settings=data)
        loaded = s.get_settings(chat_id=123456)
        assert loaded["price_from"] == 50000
        assert loaded["rooms"] == [1, 2]

    def test_update_settings_merges(self, db_path):
        """update_settings() merges with existing, doesn't overwrite all."""
        from krisha_bot.storage import Storage
        s = Storage(db_path)
        s.save_settings(chat_id=123456, settings={"price_from": 50000, "rooms": [2]})
        s.update_settings(chat_id=123456, updates={"price_to": 100000})
        loaded = s.get_settings(chat_id=123456)
        assert loaded["price_from"] == 50000
        assert loaded["price_to"] == 100000

    def test_settings_isolated_per_chat_id(self, db_path):
        from krisha_bot.storage import Storage
        s = Storage(db_path)
        s.save_settings(chat_id=111, settings={"price_from": 40000})
        s.save_settings(chat_id=222, settings={"price_from": 80000})
        assert s.get_settings(chat_id=111)["price_from"] == 40000
        assert s.get_settings(chat_id=222)["price_from"] == 80000

    def test_get_active_chats(self, db_path):
        """get_active_chats() returns chat IDs that have settings and are active."""
        from krisha_bot.storage import Storage
        s = Storage(db_path)
        s.save_settings(chat_id=111, settings={"active": True})
        s.save_settings(chat_id=222, settings={"active": False})
        active = s.get_active_chats()
        assert 111 in active
        assert 222 not in active
