"""Tests for Telegram bot command handlers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_update(text: str, chat_id: int = 123456):
    """Helper: create a fake Telegram Update object."""
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def make_context(storage=None):
    ctx = MagicMock()
    ctx.bot_data = {"storage": storage or MagicMock()}
    return ctx


class TestStartCommand:
    @pytest.mark.asyncio
    async def test_start_replies_with_welcome(self):
        from krisha_bot.bot import cmd_start
        update = make_update("/start")
        ctx = make_context()
        await cmd_start(update, ctx)
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args.args[0]
        assert "krisha" in text.lower() or "привет" in text.lower() or "бот" in text.lower()


class TestSetPriceCommand:
    @pytest.mark.asyncio
    async def test_setprice_saves_price_range(self):
        from krisha_bot.bot import cmd_setprice
        storage = MagicMock()
        storage.get_settings.return_value = {}
        update = make_update("/setprice 50000 120000")
        ctx = make_context(storage)
        ctx.args = ["50000", "120000"]
        await cmd_setprice(update, ctx)
        storage.update_settings.assert_called_once()
        call_kwargs = storage.update_settings.call_args.kwargs
        updates = call_kwargs.get("updates") or storage.update_settings.call_args.args[1]
        assert updates.get("price_from") == 50000
        assert updates.get("price_to") == 120000

    @pytest.mark.asyncio
    async def test_setprice_replies_confirmation(self):
        from krisha_bot.bot import cmd_setprice
        storage = MagicMock()
        storage.get_settings.return_value = {}
        update = make_update("/setprice 50000 120000")
        ctx = make_context(storage)
        ctx.args = ["50000", "120000"]
        await cmd_setprice(update, ctx)
        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_setprice_invalid_args_replies_error(self):
        from krisha_bot.bot import cmd_setprice
        update = make_update("/setprice abc")
        ctx = make_context()
        ctx.args = ["abc"]
        await cmd_setprice(update, ctx)
        text = update.message.reply_text.call_args.args[0]
        assert "ошибка" in text.lower() or "формат" in text.lower() or "пример" in text.lower()


class TestSetRoomsCommand:
    @pytest.mark.asyncio
    async def test_setrooms_saves_rooms(self):
        from krisha_bot.bot import cmd_setrooms
        storage = MagicMock()
        storage.get_settings.return_value = {}
        update = make_update("/setrooms 1 2")
        ctx = make_context(storage)
        ctx.args = ["1", "2"]
        await cmd_setrooms(update, ctx)
        storage.update_settings.assert_called_once()
        updates = storage.update_settings.call_args.kwargs.get("updates") or {}
        assert 1 in updates.get("rooms", [])
        assert 2 in updates.get("rooms", [])


class TestPauseResumeCommand:
    @pytest.mark.asyncio
    async def test_pause_sets_active_false(self):
        from krisha_bot.bot import cmd_pause
        storage = MagicMock()
        update = make_update("/pause")
        ctx = make_context(storage)
        await cmd_pause(update, ctx)
        storage.update_settings.assert_called_once()
        updates = storage.update_settings.call_args.kwargs.get("updates") or {}
        assert updates.get("active") is False

    @pytest.mark.asyncio
    async def test_resume_sets_active_true(self):
        from krisha_bot.bot import cmd_resume
        storage = MagicMock()
        update = make_update("/resume")
        ctx = make_context(storage)
        await cmd_resume(update, ctx)
        storage.update_settings.assert_called_once()
        updates = storage.update_settings.call_args.kwargs.get("updates") or {}
        assert updates.get("active") is True


class TestFiltersCommand:
    @pytest.mark.asyncio
    async def test_filters_shows_current_settings(self):
        from krisha_bot.bot import cmd_filters
        storage = MagicMock()
        storage.get_settings.return_value = {
            "price_from": 50000,
            "price_to": 120000,
            "rooms": [1, 2],
            "active": True,
        }
        update = make_update("/filters")
        ctx = make_context(storage)
        await cmd_filters(update, ctx)
        text = update.message.reply_text.call_args.args[0]
        assert "50" in text or "50000" in text
        assert "120" in text or "120000" in text

    @pytest.mark.asyncio
    async def test_filters_shows_not_configured_when_no_settings(self):
        from krisha_bot.bot import cmd_filters
        storage = MagicMock()
        storage.get_settings.return_value = None
        update = make_update("/filters")
        ctx = make_context(storage)
        await cmd_filters(update, ctx)
        text = update.message.reply_text.call_args.args[0].lower()
        assert "настройки" in text or "не" in text or "нет" in text


class TestIntervalCommand:
    @pytest.mark.asyncio
    async def test_interval_saves_seconds(self):
        from krisha_bot.bot import cmd_interval
        storage = MagicMock()
        update = make_update("/interval 60")
        ctx = make_context(storage)
        ctx.args = ["60"]
        await cmd_interval(update, ctx)
        storage.update_settings.assert_called_once()
        updates = storage.update_settings.call_args.kwargs.get("updates") or {}
        assert updates.get("interval_seconds") == 60

    @pytest.mark.asyncio
    async def test_interval_rejects_zero(self):
        from krisha_bot.bot import cmd_interval
        update = make_update("/interval 0")
        ctx = make_context()
        ctx.args = ["0"]
        await cmd_interval(update, ctx)
        text = update.message.reply_text.call_args.args[0].lower()
        assert "ошибка" in text or "минут" in text or "минимум" in text


class TestSetAreaCommand:
    @pytest.mark.asyncio
    async def test_setarea_saves_url(self):
        from krisha_bot.bot import cmd_setarea
        storage = MagicMock()
        url = "https://krisha.kz/arenda/kvartiry/astana/?bounds=71.41%2C51.16"
        update = make_update(f"/setarea {url}")
        ctx = make_context(storage)
        ctx.args = [url]
        await cmd_setarea(update, ctx)
        storage.update_settings.assert_called_once()
        updates = storage.update_settings.call_args.kwargs.get("updates") or {}
        assert updates.get("polygon_url") == url

    @pytest.mark.asyncio
    async def test_setarea_rejects_non_krisha_url(self):
        from krisha_bot.bot import cmd_setarea
        update = make_update("/setarea https://evil.com/hack")
        ctx = make_context()
        ctx.args = ["https://evil.com/hack"]
        await cmd_setarea(update, ctx)
        text = update.message.reply_text.call_args.args[0].lower()
        assert "krisha.kz" in text or "ошибка" in text or "неверн" in text
