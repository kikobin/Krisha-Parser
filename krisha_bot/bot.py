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
        "/history 5 — последние N найденных объявлений\n"
        "/stats — статистика\n"
        "/pause — приостановить\n"
        "/resume — возобновить\n"
        "/test — проверить настройки прямо сейчас"
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
    lines.append(f"Статус: {'активен ✅' if settings.get('active') else 'на паузе ⏸'}")

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


async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = context.bot_data["storage"]
    parser = context.bot_data.get("parser")
    notifier = context.bot_data.get("notifier")
    chat_id = update.effective_chat.id

    settings = storage.get_settings(chat_id=chat_id)
    if not settings or not settings.get("search_url"):
        await update.message.reply_text("Сначала задай область: /setarea <URL>")
        return

    try:
        from krisha_bot.filters import Filter, GeoFilter
        url = parser.build_url_from_krisha_url(settings["search_url"])

        await update.message.reply_text(f"Запрос:\n<code>{url}</code>", parse_mode="HTML")

        html = parser.fetch_page(url)
        listings = parser.parse_page(html)

        if not listings:
            snippet = html[:300].replace("<", "&lt;").replace(">", "&gt;")
            await update.message.reply_text(
                f"Парсер вернул 0 объявлений.\n"
                f"Начало страницы:\n<code>{snippet}</code>",
                parse_mode="HTML",
            )
            return

        attr_filter = Filter.from_dict(settings)
        geo = GeoFilter.from_url(settings.get("polygon_url", ""))

        after_geo = [l for l in listings if geo.matches(l)]
        matched = [l for l in after_geo if attr_filter.matches(l)]

        status = (
            f"Всего на странице: {len(listings)}\n"
            f"После геофильтра: {len(after_geo)}\n"
            f"После фильтра цены/комнат: {len(matched)}"
        )

        if not matched:
            await update.message.reply_text(status)
            return

        await notifier.send_listing(chat_id=chat_id, listing=matched[0])
        await update.message.reply_text(status)

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


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

    parser = context.bot_data.get("parser")
    search_url = parser.build_url_from_krisha_url(url) if parser else url

    storage.update_settings(
        chat_id=update.effective_chat.id,
        updates={"polygon_url": url, "search_url": search_url, "active": True},
    )
    await update.message.reply_text("Область поиска обновлена. Мониторинг запущен.")


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = context.bot_data["storage"]
    notifier = context.bot_data.get("notifier")
    chat_id = update.effective_chat.id

    try:
        n = int((context.args or ["5"])[0])
        n = max(1, min(n, 20))
    except (ValueError, IndexError):
        n = 5

    listings = storage.get_history(chat_id, limit=n)
    if not listings:
        await update.message.reply_text("История пустая — жди новых объявлений!")
        return

    await update.message.reply_text(f"Последние {len(listings)} объявлений:")
    for listing in listings:
        await notifier.send_listing(chat_id=chat_id, listing=listing)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = context.bot_data["storage"]
    chat_id = update.effective_chat.id

    stats = storage.get_stats(chat_id)
    settings = storage.get_settings(chat_id) or {}
    interval = settings.get("interval_minutes", "?")

    lines = [
        "<b>Статистика</b>",
        f"Сегодня найдено: {stats['today']}",
        f"Всего найдено: {stats['total']}",
        f"Скрыто объявлений: {stats['blacklisted']}",
        f"Интервал проверки: каждые {interval} мин.",
        f"Статус: {'активен ✅' if settings.get('active') else 'на паузе ⏸'}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def callback_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Скрыто")

    storage = context.bot_data["storage"]
    data = query.data or ""
    if not data.startswith("skip:"):
        return

    listing_id = data[len("skip:"):]
    chat_id = query.message.chat_id
    storage.blacklist(listing_id, chat_id)

    try:
        if query.message.caption is not None:
            await query.edit_message_caption(caption="🚫 Скрыто", reply_markup=None)
        else:
            await query.edit_message_text(text="🚫 Скрыто", reply_markup=None)
    except Exception:
        pass
