"""Tests for listing filter logic."""

import pytest
from tests.fixtures import SAMPLE_LISTING, SAMPLE_LISTING_2


class TestFilters:
    """Tests for Filter.matches() — returns True if listing passes all criteria."""

    def test_listing_passes_empty_filters(self):
        from krisha_bot.filters import Filter
        f = Filter()
        assert f.matches(SAMPLE_LISTING) is True

    def test_filter_by_min_price(self):
        from krisha_bot.filters import Filter
        f = Filter(price_from=90000)
        assert f.matches(SAMPLE_LISTING) is False  # price=80000 < 90000

    def test_filter_by_max_price(self):
        from krisha_bot.filters import Filter
        f = Filter(price_to=70000)
        assert f.matches(SAMPLE_LISTING) is False  # price=80000 > 70000

    def test_filter_price_in_range(self):
        from krisha_bot.filters import Filter
        f = Filter(price_from=60000, price_to=100000)
        assert f.matches(SAMPLE_LISTING) is True

    def test_filter_by_rooms_match(self):
        from krisha_bot.filters import Filter
        f = Filter(rooms=[2])
        assert f.matches(SAMPLE_LISTING) is True

    def test_filter_by_rooms_no_match(self):
        from krisha_bot.filters import Filter
        f = Filter(rooms=[1, 3])
        assert f.matches(SAMPLE_LISTING) is False  # listing has 2 rooms

    def test_filter_by_min_area(self):
        from krisha_bot.filters import Filter
        f = Filter(area_from=60)
        assert f.matches(SAMPLE_LISTING) is False  # area=55

    def test_filter_by_max_area(self):
        from krisha_bot.filters import Filter
        f = Filter(area_to=50)
        assert f.matches(SAMPLE_LISTING) is False  # area=55

    def test_filter_area_in_range(self):
        from krisha_bot.filters import Filter
        f = Filter(area_from=40, area_to=60)
        assert f.matches(SAMPLE_LISTING) is True

    def test_filter_owner_only(self):
        from krisha_bot.filters import Filter
        f = Filter(owner_only=True)
        assert f.matches(SAMPLE_LISTING) is True   # is_owner=True
        assert f.matches(SAMPLE_LISTING_2) is False  # is_owner=False

    def test_filter_not_first_floor(self):
        from krisha_bot.filters import Filter
        listing = {**SAMPLE_LISTING, "floor": 1}
        f = Filter(not_first_floor=True)
        assert f.matches(listing) is False

    def test_filter_not_last_floor(self):
        from krisha_bot.filters import Filter
        listing = {**SAMPLE_LISTING, "floor": 9, "total_floors": 9}
        f = Filter(not_last_floor=True)
        assert f.matches(listing) is False

    def test_filter_new_building_only(self):
        from krisha_bot.filters import Filter
        f = Filter(new_building_only=True)
        assert f.matches(SAMPLE_LISTING) is False   # is_new_building=False
        assert f.matches(SAMPLE_LISTING_2) is True  # is_new_building=True

    def test_multiple_filters_all_must_pass(self):
        from krisha_bot.filters import Filter
        f = Filter(price_from=60000, price_to=100000, rooms=[2], owner_only=True)
        assert f.matches(SAMPLE_LISTING) is True

    def test_multiple_filters_one_fails(self):
        from krisha_bot.filters import Filter
        f = Filter(price_from=60000, price_to=100000, rooms=[2], owner_only=True)
        listing = {**SAMPLE_LISTING, "price": 110000}
        assert f.matches(listing) is False

    def test_filter_to_dict_and_from_dict(self):
        """Filter survives round-trip through dict serialization."""
        from krisha_bot.filters import Filter
        f = Filter(price_from=50000, price_to=120000, rooms=[1, 2], owner_only=True)
        d = f.to_dict()
        f2 = Filter.from_dict(d)
        assert f2.price_from == 50000
        assert f2.rooms == [1, 2]
        assert f2.owner_only is True

    def test_filter_rooms_accepts_studio_as_zero(self):
        """Rooms=0 means studio (студия)."""
        from krisha_bot.filters import Filter
        listing = {**SAMPLE_LISTING, "rooms": 0}
        f = Filter(rooms=[0, 1])
        assert f.matches(listing) is True


class TestGeoFilter:
    """Tests for polygon-based geo filtering."""

    def test_point_inside_polygon_passes(self):
        from krisha_bot.filters import GeoFilter
        from tests.fixtures import SAMPLE_POLYGON
        geo = GeoFilter(polygon=SAMPLE_POLYGON)
        # SAMPLE_LISTING coordinates are inside the polygon
        assert geo.matches(SAMPLE_LISTING) is True

    def test_point_outside_polygon_fails(self):
        from krisha_bot.filters import GeoFilter
        from tests.fixtures import SAMPLE_POLYGON
        geo = GeoFilter(polygon=SAMPLE_POLYGON)
        listing_outside = {**SAMPLE_LISTING, "lat": 51.3000, "lon": 71.6000}
        assert geo.matches(listing_outside) is False

    def test_listing_without_coordinates_is_passed(self):
        """Listing with no lat/lon passes — trust server-side areas= filtering."""
        from krisha_bot.filters import GeoFilter
        from tests.fixtures import SAMPLE_POLYGON
        geo = GeoFilter(polygon=SAMPLE_POLYGON)
        listing_no_coords = {**SAMPLE_LISTING, "lat": None, "lon": None}
        assert geo.matches(listing_no_coords) is True

    def test_no_polygon_passes_all(self):
        """GeoFilter with no polygon accepts everything."""
        from krisha_bot.filters import GeoFilter
        geo = GeoFilter(polygon=None)
        assert geo.matches(SAMPLE_LISTING) is True

    def test_polygon_from_url(self):
        """GeoFilter.from_url() parses polygon from krisha.kz URL."""
        from krisha_bot.filters import GeoFilter
        url = "https://krisha.kz/arenda/kvartiry/astana/?bounds=71.41%2C51.16%3B71.49%2C51.20"
        geo = GeoFilter.from_url(url)
        assert geo.polygon is not None
        assert len(geo.polygon) >= 2
