from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для мониторинга объявлений на krisha.kz.\n\n"
        "Команды:\n"
        "/setprice 50000 120000 — диапазон цены (₸/мес)\n"
        "/setrooms 1 2 — количество комнат\n"
        "/setarea <URL> — область поиска (URL с krisha.kz)\n"
        "/interval 5 — проверять каждые N минут\n"
        "/filters — текущие настройки\n"
        "/pause — приостановить\n"
        "/resume — возобновить"
    )


async def cmd_setprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = context.bot_data["storage"]
    try:
        args = context.args or []
        if len(args) < 2:
            raise ValueError("need 2 args")
        price_from = int(args[0])
        price_to = int(args[1])
        if price_from < 0 or price_to < 0:
            raise ValueError("negative price")
    except (ValueError, IndexError):
        await update.message.reply_text(
            "Ошибка формата. Пример: /setprice 50000 120000"
        )
        return

    storage.update_settings(
        chat_id=update.effective_chat.id,
        updates={"price_from": price_from, "price_to": price_to},
    )
    await update.message.reply_text(
        f"Цена: {price_from:,} — {price_to:,} ₸/мес".replace(",", " ")
    )


async def cmd_setrooms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = context.bot_data["storage"]
    try:
        rooms = [int(r) for r in (context.args or [])]
        if not rooms:
            raise ValueError("empty")
    except ValueError:
        await update.message.reply_text("Пример: /setrooms 1 2")
        return

    storage.update_settings(
        chat_id=update.effective_chat.id,
        updates={"rooms": rooms},
    )
    await update.message.reply_text(f"Комнаты: {rooms}")


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = context.bot_data["storage"]
    storage.update_settings(
        chat_id=update.effective_chat.id,
        updates={"active": False},
    )
    await update.message.reply_text("Мониторинг приостановлен. /resume чтобы возобновить.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = context.bot_data["storage"]
    storage.update_settings(
        chat_id=update.effective_chat.id,
        updates={"active": True},
    )
    await update.message.reply_text("Мониторинг возобновлён.")


async def cmd_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = context.bot_data["storage"]
    settings = storage.get_settings(chat_id=update.effective_chat.id)

    if not settings:
        await update.message.reply_text(
            "Настройки не заданы. Начни с /setprice и /setarea"
        )
        return

    lines = ["Текущие настройки:"]
    if settings.get("price_from") is not None:
        lines.append(f"Цена от: {settings['price_from']:,} ₸".replace(",", " "))
    if settings.get("price_to") is not None:
        lines.append(f"Цена до: {settings['price_to']:,} ₸".replace(",", " "))
    if settings.get("rooms"):
        lines.append(f"Комнаты: {settings['rooms']}")
    if settings.get("interval_minutes"):
        lines.append(f"Интервал: {settings['interval_minutes']} мин.")
    lines.append(f"Статус: {'активен' if settings.get('active') else 'на паузе'}")

    await update.message.reply_text("\n".join(lines))


async def cmd_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = context.bot_data["storage"]
    try:
        minutes = int((context.args or ["0"])[0])
        if minutes <= 0:
            raise ValueError("must be positive")
    except (ValueError, IndexError):
        await update.message.reply_text(
            "Минимум 1 минута. Пример: /interval 5"
        )
        return

    storage.update_settings(
        chat_id=update.effective_chat.id,
        updates={"interval_minutes": minutes},
    )
    await update.message.reply_text(f"Интервал: каждые {minutes} мин.")


async def cmd_setarea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = context.bot_data["storage"]
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Укажи URL из krisha.kz. Пример:\n/setarea https://krisha.kz/map/arenda/..."
        )
        return

    url = args[0]
    if "krisha.kz" not in url:
        await update.message.reply_text(
            "Ошибка: URL должен быть с krisha.kz"
        )
        return

    storage.update_settings(
        chat_id=update.effective_chat.id,
        updates={"polygon_url": url, "search_url": url, "active": True},
    )
    await update.message.reply_text("Область поиска обновлена. Мониторинг запущен.")
