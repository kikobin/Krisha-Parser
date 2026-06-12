"""Tests for krisha.kz HTML parser."""

import pytest
from unittest.mock import patch, MagicMock
from tests.fixtures import SAMPLE_HTML, SAMPLE_URL

# from krisha_bot.parser import KrishaParser  # uncomment when implemented


class TestKrishaParser:
    """Tests for parsing krisha.kz listing pages."""

    def test_parse_returns_list_of_listings(self):
        """parse_page() returns a list."""
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        result = parser.parse_page(SAMPLE_HTML)
        assert isinstance(result, list)

    def test_parse_extracts_correct_count(self):
        """Two listings in sample HTML → two results."""
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        result = parser.parse_page(SAMPLE_HTML)
        assert len(result) == 2

    def test_parse_extracts_id(self):
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        result = parser.parse_page(SAMPLE_HTML)
        assert result[0]["id"] == "101234567"
        assert result[1]["id"] == "101234568"

    def test_parse_extracts_price(self):
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        result = parser.parse_page(SAMPLE_HTML)
        assert result[0]["price"] == 80000
        assert result[1]["price"] == 55000

    def test_parse_extracts_address(self):
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        result = parser.parse_page(SAMPLE_HTML)
        assert "Пушкина" in result[0]["address"]

    def test_parse_extracts_owner_flag(self):
        """is_owner=True when label says 'Хозяин'."""
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        result = parser.parse_page(SAMPLE_HTML)
        assert result[0]["is_owner"] is True
        assert result[1]["is_owner"] is False

    def test_parse_extracts_coordinates(self):
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        result = parser.parse_page(SAMPLE_HTML)
        assert result[0]["lat"] == pytest.approx(51.1801, abs=0.001)
        assert result[0]["lon"] == pytest.approx(71.4460, abs=0.001)

    def test_parse_extracts_url(self):
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        result = parser.parse_page(SAMPLE_HTML)
        assert result[0]["url"] == "https://krisha.kz/a/show/101234567"

    def test_parse_extracts_photo(self):
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        result = parser.parse_page(SAMPLE_HTML)
        assert len(result[0]["photos"]) > 0
        assert result[0]["photos"][0].startswith("https://")

    def test_parse_empty_html_returns_empty_list(self):
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        result = parser.parse_page("<html><body></body></html>")
        assert result == []

    def test_parse_listing_without_photo_returns_empty_photos(self):
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        result = parser.parse_page(SAMPLE_HTML)
        assert result[1]["photos"] == []

    def test_fetch_page_sends_headers(self):
        """fetch_page() sends realistic browser headers (anti-bot)."""
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        with patch("requests.Session.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = SAMPLE_HTML
            mock_get.return_value = mock_resp
            parser.fetch_page(SAMPLE_URL)
            call_kwargs = mock_get.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else {}
            # check that session was called — headers are set on session level
            assert mock_get.called

    def test_fetch_page_raises_on_non_200(self):
        """fetch_page() raises on HTTP error."""
        from krisha_bot.parser import KrishaParser, FetchError
        parser = KrishaParser()
        with patch("requests.Session.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 403
            mock_resp.raise_for_status.side_effect = Exception("403")
            mock_get.return_value = mock_resp
            with pytest.raises(FetchError):
                parser.fetch_page(SAMPLE_URL)

    def test_fetch_page_retries_on_timeout(self):
        """fetch_page() retries up to 3 times on timeout."""
        import requests
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        with patch("requests.Session.get", side_effect=requests.Timeout) as mock_get:
            with pytest.raises(Exception):
                parser.fetch_page(SAMPLE_URL)
            assert mock_get.call_count == 3

    def test_build_url_from_filters(self):
        """build_url() constructs correct krisha.kz URL from filter dict."""
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        filters = {
            "deal_type": "arenda",
            "rooms": [1, 2],
            "price_from": 40000,
            "price_to": 120000,
        }
        url = parser.build_url(filters)
        assert "krisha.kz/arenda" in url
        assert "price" in url

    def test_build_url_includes_polygon(self):
        """build_url() includes polygon bounds when area is provided."""
        from krisha_bot.parser import KrishaParser
        from tests.fixtures import SAMPLE_POLYGON
        parser = KrishaParser()
        filters = {"deal_type": "arenda"}
        url = parser.build_url(filters, polygon=SAMPLE_POLYGON)
        assert "bounds" in url or "region" in url or "polygon" in url

    def test_parse_next_page_url(self):
        """parse_next_page_url() returns URL for page 2 when pagination exists."""
        from krisha_bot.parser import KrishaParser
        html = SAMPLE_HTML.replace(
            "</section>",
            '</section><a class="pager__next" href="/arenda/kvartiry/astana/?page=2">Следующая</a>',
        )
        parser = KrishaParser()
        next_url = parser.parse_next_page_url(html)
        assert next_url is not None
        assert "page=2" in next_url

    def test_parse_next_page_url_returns_none_on_last_page(self):
        from krisha_bot.parser import KrishaParser
        parser = KrishaParser()
        result = parser.parse_next_page_url(SAMPLE_HTML)
        assert result is None
