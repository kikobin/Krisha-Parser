"""Tests for speed — being FIRST requires low latency."""

import pytest
import time
from unittest.mock import patch, MagicMock
from tests.fixtures import SAMPLE_HTML, SAMPLE_LISTING


class TestSpeed:
    """Parsing and filtering must be fast — we want to be first."""

    def test_parse_page_under_100ms(self):
        """Parsing one page of HTML must complete in under 100ms."""
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        start = time.perf_counter()
        for _ in range(10):
            parser.parse_page(SAMPLE_HTML)
        elapsed = (time.perf_counter() - start) / 10
        assert elapsed < 0.1, f"parse_page took {elapsed:.3f}s — too slow"

    def test_filter_matches_under_1ms(self):
        """Checking one listing against filters must take under 1ms."""
        from krisha_bot.filters import Filter
        f = Filter(price_from=50000, price_to=120000, rooms=[2], owner_only=True)
        start = time.perf_counter()
        for _ in range(1000):
            f.matches(SAMPLE_LISTING)
        elapsed = (time.perf_counter() - start) / 1000
        assert elapsed < 0.001, f"filter.matches took {elapsed:.4f}s — too slow"

    def test_storage_is_seen_under_5ms(self, tmp_path):
        """is_seen() lookup must be under 5ms (indexed query)."""
        from krisha_bot.storage import Storage
        s = Storage(str(tmp_path / "speed_test.db"))
        for i in range(10000):
            s.mark_seen(str(i))
        start = time.perf_counter()
        for i in range(100):
            s.is_seen("99999")
        elapsed = (time.perf_counter() - start) / 100
        assert elapsed < 0.005, f"is_seen took {elapsed:.4f}s — too slow"

    def test_full_tick_under_2_seconds(self, tmp_path):
        """A full monitor tick (excluding network) must be under 2s."""
        import asyncio
        from krisha_bot.monitor import Monitor
        from krisha_bot.filters import Filter
        from unittest.mock import AsyncMock

        parser = MagicMock()
        parser.fetch_page.return_value = SAMPLE_HTML
        parser.parse_page.return_value = [SAMPLE_LISTING]
        parser.build_url.return_value = "https://krisha.kz/test"
        parser.parse_next_page_url.return_value = None

        storage = MagicMock()
        storage.filter_new.return_value = [SAMPLE_LISTING]

        notifier = MagicMock()
        notifier.send_batch = AsyncMock()

        monitor = Monitor(parser=parser, storage=storage, notifier=notifier)
        f = Filter()

        start = time.perf_counter()
        asyncio.get_event_loop().run_until_complete(
            monitor.tick(chat_id=123456, filters=f, url="https://krisha.kz/test")
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"tick() took {elapsed:.2f}s — too slow"
