from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse, parse_qs, unquote


@dataclass
class Filter:
    price_from: Optional[int] = None
    price_to: Optional[int] = None
    rooms: List[int] = field(default_factory=list)
    area_from: Optional[float] = None
    area_to: Optional[float] = None
    owner_only: bool = False
    not_first_floor: bool = False
    not_last_floor: bool = False
    new_building_only: bool = False

    def matches(self, listing: dict) -> bool:
        price = listing.get("price", 0)
        if self.price_from is not None and price < self.price_from:
            return False
        if self.price_to is not None and price > self.price_to:
            return False

        if self.rooms:
            if listing.get("rooms") not in self.rooms:
                return False

        area = listing.get("area", 0.0)
        if self.area_from is not None and area < self.area_from:
            return False
        if self.area_to is not None and area > self.area_to:
            return False

        if self.owner_only and not listing.get("is_owner"):
            return False

        floor = listing.get("floor", 0)
        total = listing.get("total_floors", 0)
        if self.not_first_floor and floor == 1:
            return False
        if self.not_last_floor and total > 0 and floor == total:
            return False

        if self.new_building_only and not listing.get("is_new_building"):
            return False

        return True

    def to_dict(self) -> dict:
        return {
            "price_from": self.price_from,
            "price_to": self.price_to,
            "rooms": list(self.rooms),
            "area_from": self.area_from,
            "area_to": self.area_to,
            "owner_only": self.owner_only,
            "not_first_floor": self.not_first_floor,
            "not_last_floor": self.not_last_floor,
            "new_building_only": self.new_building_only,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Filter:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


class GeoFilter:
    """Point-in-polygon filter. Supports multiple polygons (union)."""

    def __init__(self, polygon):
        # polygon: list of (lon, lat) tuples, or None
        # For multi-polygon support store as list-of-polygons
        if polygon is None:
            self._polygons = []
        elif polygon and isinstance(polygon[0][0], (list, tuple)):
            self._polygons = polygon  # already list of polygons
        else:
            self._polygons = [polygon]

    @property
    def polygon(self):
        """Return first polygon for backward compat, or None."""
        return self._polygons[0] if self._polygons else None

    def matches(self, listing: dict) -> bool:
        if not self._polygons:
            return True
        lat = listing.get("lat")
        lon = listing.get("lon")
        if lat is None or lon is None:
            return True  # no coords in HTML — trust server-side areas= param
        return any(_point_in_polygon(lon, lat, p) for p in self._polygons)

    @classmethod
    def from_url(cls, url: str) -> GeoFilter:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # areas= parameter: p{lat},{lon},{lat},{lon},...,p{lat},...
        if "areas" in params:
            areas_str = unquote(params["areas"][0])
            polygons = _parse_areas(areas_str)
            if polygons:
                obj = cls(polygon=None)
                obj._polygons = polygons
                return obj

        # bounds= parameter: lon1,lat1;lon2,lat2
        if "bounds" in params:
            polygon = _parse_bounds(params["bounds"][0])
            if polygon:
                return cls(polygon=polygon)

        return cls(polygon=None)


# ------------------------------------------------------------------
# Geometry helpers
# ------------------------------------------------------------------

def _point_in_polygon(x: float, y: float, polygon: list) -> bool:
    """Ray-casting algorithm. polygon is [(lon, lat), ...]."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y):
            if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def _parse_areas(areas_str: str) -> list:
    """
    Parse krisha.kz areas parameter.
    Format: p{lat},{lon},{lat},{lon},...,p{lat},{lon},...
    Returns list of polygons, each polygon is [(lon, lat), ...].
    """
    polygons = []
    parts = areas_str.split("p")
    for part in parts:
        part = part.strip(",")
        if not part:
            continue
        try:
            nums = [float(x) for x in part.split(",") if x.strip()]
        except ValueError:
            continue
        if len(nums) < 4:
            continue
        # nums are lat,lon pairs
        poly = [(nums[i + 1], nums[i]) for i in range(0, len(nums) - 1, 2)]
        polygons.append(poly)
    return polygons


def _parse_bounds(bounds: str):
    """bounds=lon1,lat1;lon2,lat2 → bounding box as polygon."""
    try:
        p1, p2 = bounds.split(";")
        lon1, lat1 = map(float, p1.split(","))
        lon2, lat2 = map(float, p2.split(","))
        return [
            (lon1, lat1), (lon2, lat1),
            (lon2, lat2), (lon1, lat2),
            (lon1, lat1),
        ]
    except Exception:
        return None
