import re
import time
import json
import logging
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_URL = "https://krisha.kz"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://krisha.kz/",
}


class FetchError(Exception):
    pass


class KrishaParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    def fetch_page(self, url: str, retries: int = 3) -> str:
        last_exc = None
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code != 200:
                    try:
                        resp.raise_for_status()
                    except Exception as e:
                        raise FetchError(str(e)) from e
                    raise FetchError(f"HTTP {resp.status_code}")
                return resp.text
            except requests.Timeout as e:
                last_exc = e
                if attempt < retries - 1:
                    time.sleep(1)
            except FetchError:
                raise
            except Exception as e:
                raise FetchError(str(e)) from e
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse_page(self, html: str) -> list:
        soup = BeautifulSoup(html, "lxml")

        # Extract coordinates from window.data JSON (injected by server)
        coords_map = _extract_coords(html)

        results = []
        for card in soup.select(".a-card"):
            listing = self._parse_card(card, coords_map)
            if listing:
                results.append(listing)
        return results

    def _parse_card(self, card, coords_map: dict = None):
        listing_id = card.get("data-id")
        if not listing_id:
            return None

        # Title & URL — real site uses .a-card__title as <a>
        title_el = card.select_one(".a-card__title")
        title = title_el.get_text(strip=True) if title_el else ""
        url = ""
        if title_el and title_el.get("href"):
            href = title_el["href"]
            url = href if href.startswith("http") else BASE_URL + href
        # Fallback: link on image
        if not url:
            img_link = card.select_one("a.a-card__image")
            if img_link and img_link.get("href"):
                href = img_link["href"]
                url = href if href.startswith("http") else BASE_URL + href

        # Price — grab only text nodes (ignore currency span)
        price = 0
        price_el = card.select_one(".a-card__price")
        if price_el:
            price = _parse_price(price_el.get_text())

        # Address — real site: .a-card__subtitle  (tests use .a-card__description)
        address = ""
        for sel in [".a-card__subtitle", ".a-card__description"]:
            addr_el = card.select_one(sel)
            if addr_el:
                address = addr_el.get_text(strip=True)
                break

        # Owner — real site has label text inside .a-card__owner
        is_owner = False
        owner_el = card.select_one(".a-card__owner")
        if owner_el:
            owner_text = owner_el.get_text()
            is_owner = "Хозяин" in owner_text

        # Photo
        photos = []
        img = card.select_one("a.a-card__image img, .a-card__img")
        if img:
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("http"):
                photos = [src]

        # Coordinates from window.data
        lat = lon = None
        if coords_map and listing_id in coords_map:
            lat, lon = coords_map[listing_id]
        else:
            lat_el = card.select_one('[itemprop="latitude"]')
            lon_el = card.select_one('[itemprop="longitude"]')
            if lat_el and lat_el.get("content"):
                lat = float(lat_el["content"])
            if lon_el and lon_el.get("content"):
                lon = float(lon_el["content"])

        rooms, area, floor, total_floors = _parse_title(title)

        # New building
        is_new = bool(
            card.select_one(".a-card__new-building")
            or card.select_one('[class*="newbuilding"]')
        )

        # Published date
        published_at = None
        for stat in card.select(".a-card__stats-item"):
            t = stat.get_text(strip=True)
            if re.search(r"\d+\s+\w+", t):
                published_at = t
                break

        return {
            "id": listing_id,
            "title": title,
            "price": price,
            "currency": "KZT",
            "address": address,
            "rooms": rooms,
            "area": area,
            "floor": floor,
            "total_floors": total_floors,
            "is_new_building": is_new,
            "is_owner": is_owner,
            "lat": lat,
            "lon": lon,
            "photos": photos,
            "url": url,
            "published_at": published_at,
        }

    def parse_next_page_url(self, html: str):
        soup = BeautifulSoup(html, "lxml")
        el = soup.select_one(".pager__next")
        if el and el.get("href"):
            href = el["href"]
            return href if href.startswith("http") else BASE_URL + href
        return None

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------

    def build_url(self, filters: dict, polygon=None) -> str:
        deal = filters.get("deal_type", "arenda")
        prop = filters.get("prop_type", "kvartiry")
        city = filters.get("city", "")

        if city:
            base = f"{BASE_URL}/{deal}/{prop}/{city}/"
        else:
            base = f"{BASE_URL}/{deal}/{prop}/"

        params: dict = {}
        if filters.get("price_from"):
            params["das[price][from]"] = filters["price_from"]
        if filters.get("price_to"):
            params["das[price][to]"] = filters["price_to"]
        for r in filters.get("rooms", []):
            params["das[live.rooms]"] = r

        if polygon:
            lons = [p[0] for p in polygon]
            lats = [p[1] for p in polygon]
            params["bounds"] = f"{min(lons)},{min(lats)};{max(lons)},{max(lats)}"

        if params:
            return base + "?" + urlencode(params)
        return base

    def build_url_from_krisha_url(self, krisha_url: str) -> str:
        """Convert map URL to list URL, preserving areas param. Injects sort=newest."""
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(krisha_url)
        path = parsed.path.replace("/map/arenda/", "/arenda/").replace("/map/prodazha/", "/prodazha/")
        params = parse_qs(parsed.query, keep_blank_values=True)
        for drop in ("zoom", "lat", "lon"):
            params.pop(drop, None)
        # Sort by newest first so we catch new listings immediately
        if "sort[0][order]" not in params:
            params["sort[0][order]"] = ["date"]
        if "sort[0][direction]" not in params:
            params["sort[0][direction]"] = ["desc"]
        query = urlencode({k: v[0] for k, v in params.items()})
        return urlunparse((parsed.scheme, parsed.netloc, path, "", query, ""))


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _extract_coords(html: str) -> dict:
    """Extract {listing_id: (lat, lon)} from window.data JSON."""
    m = re.search(r"window\.data\s*=\s*(\{.*?\});", html, re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
        coords = {}
        for item in data.get("advert", {}).get("adverts", []):
            lid = str(item.get("id", ""))
            lat = item.get("lat")
            lon = item.get("lon")
            if lid and lat and lon:
                coords[lid] = (float(lat), float(lon))
        return coords
    except Exception:
        return {}


def _parse_price(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def _parse_title(title: str):
    rooms = 0
    area = 0.0
    floor = 0
    total_floors = 0

    # Rooms: "2-комнатная" or "2 комнатная"
    m = re.search(r"(\d+)[-\s]комнатн", title)
    if m:
        rooms = int(m.group(1))

    # Area: "55 м²" or "55.5 м²" — supports both · and , separators
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*м", title)
    if m:
        area = float(m.group(1).replace(",", "."))

    # Floor: "3/9 этаж" or just "8 этаж"
    m = re.search(r"(\d+)/(\d+)\s*этаж", title)
    if m:
        floor = int(m.group(1))
        total_floors = int(m.group(2))
    else:
        m = re.search(r"(\d+)\s*этаж", title)
        if m:
            floor = int(m.group(1))

    return rooms, area, floor, total_floors
