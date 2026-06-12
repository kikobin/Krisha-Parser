from __future__ import annotations

import asyncio
import logging

from telegram import Bot
from telegram.error import RetryAfter

log = logging.getLogger(__name__)


def format_listing(listing: dict) -> str:
    price = listing.get("price", 0)
    price_str = f"{price:,}".replace(",", " ")  # non-breaking space

    rooms = listing.get("rooms", 0)
    area = listing.get("area", 0)
    floor = listing.get("floor", 0)
    total_floors = listing.get("total_floors", 0)
    address = listing.get("address", "")
    url = listing.get("url", "")
    is_owner = listing.get("is_owner", False)
    is_new = listing.get("is_new_building", False)

    owner_label = "Хозяин" if is_owner else "Агентство"

    lines = [
        f"<b>{rooms}-комн. квартира, {area} м²</b>",
        f"💰 <b>{price_str} ₸/мес</b>",
        f"🏢 Этаж: {floor}/{total_floors}",
        f"📍 {address}",
        f"👤 {owner_label}",
    ]
    if is_new:
        lines.append("🏗 Новостройка")

    lines.append(f'<a href="{url}">Открыть объявление</a>')

    return "\n".join(lines)


class Notifier:
    def __init__(self, token: str):
        self._bot = Bot(token=token)

    async def send_listing(self, chat_id: int, listing: dict):
        text = format_listing(listing)
        photos = listing.get("photos", [])

        for attempt in range(3):
            try:
                if photos:
                    await self._bot.send_photo(
                        chat_id=chat_id,
                        photo=photos[0],
                        caption=text,
                        parse_mode="HTML",
                    )
                else:
                    await self._bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode="HTML",
                    )
                return
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after)

    async def send_batch(self, chat_id: int, listings: list):
        for listing in listings:
            await self.send_listing(chat_id=chat_id, listing=listing)
