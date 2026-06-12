import asyncio
import logging
import os

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from krisha_bot import bot as bot_handlers
from krisha_bot.monitor import Monitor
from krisha_bot.notifier import Notifier
from krisha_bot.parser import KrishaParser
from krisha_bot.storage import Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def main():
    token = os.environ["BOT_TOKEN"]
    db_path = os.environ.get("DB_PATH", "krisha.db")
    interval = int(os.environ.get("INTERVAL_SECONDS", "60"))

    parser = KrishaParser()
    storage = Storage(db_path)
    notifier = Notifier(token=token)
    monitor = Monitor(
        parser=parser,
        storage=storage,
        notifier=notifier,
        interval_seconds=interval,
    )

    app = (
        Application.builder()
        .token(token)
        .build()
    )
    app.bot_data["storage"] = storage
    app.bot_data["monitor"] = monitor
    app.bot_data["parser"] = parser
    app.bot_data["notifier"] = notifier

    app.add_handler(CommandHandler("start",    bot_handlers.cmd_start))
    app.add_handler(CommandHandler("setprice", bot_handlers.cmd_setprice))
    app.add_handler(CommandHandler("setrooms", bot_handlers.cmd_setrooms))
    app.add_handler(CommandHandler("setarea",  bot_handlers.cmd_setarea))
    app.add_handler(CommandHandler("filters",  bot_handlers.cmd_filters))
    app.add_handler(CommandHandler("pause",    bot_handlers.cmd_pause))
    app.add_handler(CommandHandler("resume",   bot_handlers.cmd_resume))
    app.add_handler(CommandHandler("interval", bot_handlers.cmd_interval))
    app.add_handler(CommandHandler("test",     bot_handlers.cmd_test))
    app.add_handler(CommandHandler("history",  bot_handlers.cmd_history))
    app.add_handler(CommandHandler("stats",    bot_handlers.cmd_stats))
    app.add_handler(CommandHandler("reset",    bot_handlers.cmd_reset))
    app.add_handler(CallbackQueryHandler(bot_handlers.callback_skip, pattern=r"^skip:"))

    async def post_init(application):
        asyncio.create_task(monitor.run())
        log.info("Monitor started, polling every %ds", interval)

    app.post_init = post_init

    log.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
