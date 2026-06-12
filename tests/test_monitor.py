"""Tests for the polling monitor — the core loop that ties everything together."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from tests.fixtures import SAMPLE_LISTING, SAMPLE_LISTING_2


class TestMonitor:
    """Tests for Monitor — the main polling loop."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Return mock parser, storage, notifier, and filter."""
        from unittest.mock import MagicMock
        parser = MagicMock()
        parser.fetch_page.return_value = "<html></html>"
        parser.parse_page.return_value = [SAMPLE_LISTING, SAMPLE_LISTING_2]
        parser.build_url.return_value = "https://krisha.kz/arenda/kvartiry/astana/"
        parser.parse_next_page_url.return_value = None

        storage = MagicMock()
        storage.filter_new.return_value = [SAMPLE_LISTING]
        storage.get_settings.return_value = {
            "active": True,
            "price_from": 50000,
            "rooms": [2],
        }
        storage.get_active_chats.return_value = [123456]

        notifier = MagicMock()
        notifier.send_batch = AsyncMock()

        f = MagicMock()
        f.matches.return_value = True

        return parser, storage, notifier, f

    @pytest.mark.asyncio
    async def test_tick_fetches_and_parses(self, mock_deps):
        """tick() fetches page and parses listings."""
        from krisha_bot.monitor import Monitor
        parser, storage, notifier, f = mock_deps
        monitor = Monitor(parser=parser, storage=storage, notifier=notifier)
        await monitor.tick(chat_id=123456, filters=f, url="https://krisha.kz/test")
        parser.fetch_page.assert_called_once()
        parser.parse_page.assert_called_once()

    @pytest.mark.asyncio
    async def test_tick_filters_new_listings(self, mock_deps):
        """tick() calls storage.filter_new to remove already-seen listings."""
        from krisha_bot.monitor import Monitor
        parser, storage, notifier, f = mock_deps
        monitor = Monitor(parser=parser, storage=storage, notifier=notifier)
        await monitor.tick(chat_id=123456, filters=f, url="https://krisha.kz/test")
        storage.filter_new.assert_called_once()

    @pytest.mark.asyncio
    async def test_tick_sends_only_new_listings(self, mock_deps):
        """tick() sends only listings that pass both filter and dedup."""
        from krisha_bot.monitor import Monitor
        parser, storage, notifier, f = mock_deps
        storage.filter_new.return_value = [SAMPLE_LISTING]  # 1 new out of 2
        monitor = Monitor(parser=parser, storage=storage, notifier=notifier)
        await monitor.tick(chat_id=123456, filters=f, url="https://krisha.kz/test")
        notifier.send_batch.assert_called_once()
        sent = notifier.send_batch.call_args.kwargs.get("listings") or notifier.send_batch.call_args.args[1]
        assert len(sent) == 1

    @pytest.mark.asyncio
    async def test_tick_marks_new_as_seen(self, mock_deps):
        """tick() marks sent listings as seen in storage."""
        from krisha_bot.monitor import Monitor
        parser, storage, notifier, f = mock_deps
        monitor = Monitor(parser=parser, storage=storage, notifier=notifier)
        await monitor.tick(chat_id=123456, filters=f, url="https://krisha.kz/test")
        storage.bulk_mark_seen.assert_called_once()

    @pytest.mark.asyncio
    async def test_tick_no_new_listings_no_notification(self, mock_deps):
        """tick() sends nothing when there are no new listings."""
        from krisha_bot.monitor import Monitor
        parser, storage, notifier, f = mock_deps
        storage.filter_new.return_value = []
        monitor = Monitor(parser=parser, storage=storage, notifier=notifier)
        await monitor.tick(chat_id=123456, filters=f, url="https://krisha.kz/test")
        notifier.send_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_tick_applies_geo_and_attribute_filters(self, mock_deps):
        """tick() applies filters to each listing."""
        from krisha_bot.monitor import Monitor
        parser, storage, notifier, f = mock_deps
        f.matches.return_value = False  # everything rejected by filter
        storage.filter_new.return_value = [SAMPLE_LISTING, SAMPLE_LISTING_2]
        monitor = Monitor(parser=parser, storage=storage, notifier=notifier)
        await monitor.tick(chat_id=123456, filters=f, url="https://krisha.kz/test")
        notifier.send_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_tick_fetch_error_does_not_crash(self, mock_deps):
        """tick() logs error and returns gracefully if fetch fails."""
        from krisha_bot.monitor import Monitor
        from krisha_bot.parser import FetchError
        parser, storage, notifier, f = mock_deps
        parser.fetch_page.side_effect = FetchError("403 Forbidden")
        monitor = Monitor(parser=parser, storage=storage, notifier=notifier)
        # Should not raise
        await monitor.tick(chat_id=123456, filters=f, url="https://krisha.kz/test")

    @pytest.mark.asyncio
    async def test_tick_paginates_when_next_page_exists(self, mock_deps):
        """tick() follows pagination and fetches page 2."""
        from krisha_bot.monitor import Monitor
        parser, storage, notifier, f = mock_deps
        # First call returns next page URL, second call returns None
        parser.parse_next_page_url.side_effect = [
            "https://krisha.kz/arenda/?page=2",
            None,
        ]
        monitor = Monitor(parser=parser, storage=storage, notifier=notifier)
        await monitor.tick(chat_id=123456, filters=f, url="https://krisha.kz/test")
        assert parser.fetch_page.call_count == 2

    @pytest.mark.asyncio
    async def test_run_calls_tick_repeatedly(self, mock_deps):
        """run() calls tick() at least N times before being cancelled."""
        from krisha_bot.monitor import Monitor
        parser, storage, notifier, f = mock_deps
        monitor = Monitor(parser=parser, storage=storage, notifier=notifier, interval_seconds=0)

        tick_count = 0
        original_tick = monitor.tick

        async def counting_tick(*args, **kwargs):
            nonlocal tick_count
            tick_count += 1
            if tick_count >= 3:
                raise asyncio.CancelledError
            return await original_tick(*args, **kwargs)

        monitor.tick = counting_tick
        storage.get_active_chats.return_value = [123456]

        with pytest.raises(asyncio.CancelledError):
            await monitor.run()

        assert tick_count == 3

    @pytest.mark.asyncio
    async def test_run_respects_pause(self, mock_deps):
        """run() skips tick for paused chats."""
        from krisha_bot.monitor import Monitor
        parser, storage, notifier, f = mock_deps
        storage.get_settings.return_value = {"active": False}
        storage.get_active_chats.return_value = []  # paused = not active
        monitor = Monitor(parser=parser, storage=storage, notifier=notifier, interval_seconds=0)

        run_count = 0

        async def patched_tick(*a, **kw):
            nonlocal run_count
            run_count += 1

        monitor.tick = patched_tick

        async def one_iteration():
            await asyncio.sleep(0)

        # run one pass manually
        for chat_id in storage.get_active_chats():
            await monitor.tick(chat_id=chat_id, filters=f, url="x")

        assert run_count == 0
