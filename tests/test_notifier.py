"""Tests for Telegram notification formatting and sending."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from tests.fixtures import SAMPLE_LISTING, SAMPLE_LISTING_2


class TestMessageFormatter:
    """Tests for formatting listings into Telegram messages."""

    def test_format_includes_price(self):
        from krisha_bot.notifier import format_listing
        text = format_listing(SAMPLE_LISTING)
        assert "80" in text  # 80 000 ₸

    def test_format_includes_address(self):
        from krisha_bot.notifier import format_listing
        text = format_listing(SAMPLE_LISTING)
        assert "Пушкина" in text

    def test_format_includes_url(self):
        from krisha_bot.notifier import format_listing
        text = format_listing(SAMPLE_LISTING)
        assert "krisha.kz" in text

    def test_format_includes_rooms_and_area(self):
        from krisha_bot.notifier import format_listing
        text = format_listing(SAMPLE_LISTING)
        assert "2" in text   # rooms
        assert "55" in text  # area

    def test_format_shows_owner_label(self):
        from krisha_bot.notifier import format_listing
        text = format_listing(SAMPLE_LISTING)
        assert "Хозяин" in text

    def test_format_shows_agent_label(self):
        from krisha_bot.notifier import format_listing
        text = format_listing(SAMPLE_LISTING_2)
        assert "Агент" in text or "Агентство" in text

    def test_format_shows_new_building_badge(self):
        from krisha_bot.notifier import format_listing
        text = format_listing(SAMPLE_LISTING_2)
        assert "Новостройка" in text or "новостройка" in text

    def test_format_price_formatted_with_spaces(self):
        """80000 should be displayed as '80 000', not '80000'."""
        from krisha_bot.notifier import format_listing
        text = format_listing(SAMPLE_LISTING)
        assert "80 000" in text

    def test_format_floor_info(self):
        from krisha_bot.notifier import format_listing
        text = format_listing(SAMPLE_LISTING)
        assert "3" in text and "9" in text  # floor 3/9

    def test_format_valid_telegram_html(self):
        """Output must be valid Telegram HTML (no unclosed tags)."""
        from krisha_bot.notifier import format_listing
        text = format_listing(SAMPLE_LISTING)
        # basic check: every opening tag has a closing tag
        import re
        open_tags = re.findall(r"<(\w+)(?:\s[^>]*)?>", text)
        close_tags = re.findall(r"</(\w+)>", text)
        assert sorted(open_tags) == sorted(close_tags)


class TestNotifier:
    """Tests for sending Telegram messages."""

    @pytest.fixture
    def notifier(self):
        from krisha_bot.notifier import Notifier
        return Notifier(token="fake_token_123")

    @pytest.mark.asyncio
    async def test_send_listing_calls_send_photo_when_photo_exists(self, notifier):
        with patch.object(notifier, "_bot") as mock_bot:
            mock_bot.send_photo = AsyncMock()
            await notifier.send_listing(chat_id=123456, listing=SAMPLE_LISTING)
            mock_bot.send_photo.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_listing_calls_send_message_when_no_photo(self, notifier):
        with patch.object(notifier, "_bot") as mock_bot:
            mock_bot.send_message = AsyncMock()
            await notifier.send_listing(chat_id=123456, listing=SAMPLE_LISTING_2)
            mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_listing_passes_correct_chat_id(self, notifier):
        with patch.object(notifier, "_bot") as mock_bot:
            mock_bot.send_photo = AsyncMock()
            await notifier.send_listing(chat_id=999, listing=SAMPLE_LISTING)
            call_kwargs = mock_bot.send_photo.call_args
            assert call_kwargs.kwargs.get("chat_id") == 999 or call_kwargs.args[0] == 999

    @pytest.mark.asyncio
    async def test_send_listing_includes_formatted_text(self, notifier):
        with patch.object(notifier, "_bot") as mock_bot:
            mock_bot.send_photo = AsyncMock()
            await notifier.send_listing(chat_id=123456, listing=SAMPLE_LISTING)
            call_kwargs = mock_bot.send_photo.call_args
            caption = call_kwargs.kwargs.get("caption", "")
            assert "krisha.kz" in caption or "80 000" in caption

    @pytest.mark.asyncio
    async def test_send_listing_retries_on_rate_limit(self, notifier):
        """On TelegramError rate limit, retries after delay."""
        from telegram.error import RetryAfter
        with patch.object(notifier, "_bot") as mock_bot:
            mock_bot.send_photo = AsyncMock(
                side_effect=[RetryAfter(1), None]
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await notifier.send_listing(chat_id=123456, listing=SAMPLE_LISTING)
            assert mock_bot.send_photo.call_count == 2

    @pytest.mark.asyncio
    async def test_send_batch_sends_all_listings(self, notifier):
        from tests.fixtures import SAMPLE_LISTING_2
        with patch.object(notifier, "send_listing", new_callable=AsyncMock) as mock_send:
            await notifier.send_batch(chat_id=123456, listings=[SAMPLE_LISTING, SAMPLE_LISTING_2])
            assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_send_batch_empty_list_does_nothing(self, notifier):
        with patch.object(notifier, "send_listing", new_callable=AsyncMock) as mock_send:
            await notifier.send_batch(chat_id=123456, listings=[])
            mock_send.assert_not_called()
