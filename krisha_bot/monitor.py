from __future__ import annotations

import asyncio
import logging

from krisha_bot.parser import FetchError

log = logging.getLogger(__name__)


class Monitor:
    def __init__(self, parser, storage, notifier, interval_seconds: int = 60):
        self.parser = parser
        self.storage = storage
        self.notifier = notifier
        self.interval_seconds = interval_seconds

    async def tick(self, chat_id: int, filters, url: str):
        try:
            all_listings = []
            current_url = url

            while current_url:
                html = self.parser.fetch_page(current_url)
                listings = self.parser.parse_page(html)
                all_listings.extend(listings)
                current_url = self.parser.parse_next_page_url(html)

            # Dedup first — skip already-sent and blacklisted listings
            new_listings = self.storage.filter_new(all_listings)

            # Attribute + geo filters applied only to new listings
            new_listings = [l for l in new_listings if filters.matches(l)]

            if new_listings:
                await self.notifier.send_batch(chat_id=chat_id, listings=new_listings)
                self.storage.bulk_mark_seen([l["id"] for l in new_listings])
                for listing in new_listings:
                    self.storage.save_to_history(chat_id, listing)

        except FetchError as exc:
            log.error("Fetch error for chat %s: %s", chat_id, exc)

    async def _warmup(self, chat_id: int, url: str):
        """First-run: silently mark all current listings as seen — no notifications."""
        try:
            all_ids = []
            current_url = url
            while current_url:
                html = self.parser.fetch_page(current_url)
                listings = self.parser.parse_page(html)
                all_ids.extend(l["id"] for l in listings)
                current_url = self.parser.parse_next_page_url(html)
            self.storage.bulk_mark_seen(all_ids)
            self.storage.update_settings(chat_id, {"warmed_up": True})
            log.info("Warmed up chat %s: marked %d listings as seen", chat_id, len(all_ids))
        except FetchError as exc:
            log.error("Warmup error for chat %s: %s", chat_id, exc)

    async def run(self):
        while True:
            active = self.storage.get_active_chats()
            for chat_id in active:
                settings = self.storage.get_settings(chat_id)
                if not settings:
                    continue

                from krisha_bot.filters import Filter, GeoFilter
                attr_filter = Filter.from_dict(settings)
                polygon_url = settings.get("polygon_url", "")
                geo = GeoFilter.from_url(polygon_url) if polygon_url else GeoFilter(None)

                class CombinedFilter:
                    def __init__(self, af, gf):
                        self._af = af
                        self._gf = gf
                    def matches(self, listing):
                        return self._af.matches(listing) and self._gf.matches(listing)

                combined = CombinedFilter(attr_filter, geo)
                url = settings.get("search_url") or settings.get("polygon_url", "")
                url = self.parser.build_url_from_krisha_url(url)

                # First run after /setarea: silently mark existing listings as seen.
                # Only triggers when explicitly set to False by /setarea — not on missing key.
                if settings.get("warmed_up") is False:
                    await self._warmup(chat_id, url)
                    continue

                await self.tick(chat_id=chat_id, filters=combined, url=url)

            await asyncio.sleep(self.interval_seconds)
