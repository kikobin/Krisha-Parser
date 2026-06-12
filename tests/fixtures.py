"""Shared test fixtures and sample data."""

SAMPLE_LISTING = {
    "id": "101234567",
    "title": "2-комнатная квартира, 55 м², 3/9 этаж",
    "price": 80000,
    "currency": "KZT",
    "address": "ул. Александра Пушкина, 10",
    "rooms": 2,
    "area": 55.0,
    "floor": 3,
    "total_floors": 9,
    "is_new_building": False,
    "is_owner": True,
    "lat": 51.1801,
    "lon": 71.4460,
    "photos": ["https://photos.krisha.kz/photo/1.jpg"],
    "url": "https://krisha.kz/a/show/101234567",
    "published_at": "2026-06-12T10:00:00",
}

SAMPLE_LISTING_2 = {
    "id": "101234568",
    "title": "1-комнатная квартира, 38 м², 5/12 этаж",
    "price": 55000,
    "currency": "KZT",
    "address": "просп. Абылай Хана, 5",
    "rooms": 1,
    "area": 38.0,
    "floor": 5,
    "total_floors": 12,
    "is_new_building": True,
    "is_owner": False,
    "lat": 51.1750,
    "lon": 71.4380,
    "photos": [],
    "url": "https://krisha.kz/a/show/101234568",
    "published_at": "2026-06-12T10:05:00",
}

# Polygon roughly matching the area drawn in the screenshot (Astana center)
SAMPLE_POLYGON = [
    (71.4100, 51.2000),
    (71.4700, 51.2050),
    (71.4950, 51.1950),
    (71.4850, 51.1700),
    (71.4400, 51.1600),
    (71.4050, 51.1700),
    (71.4100, 51.2000),
]

# krisha.kz URL with polygon and filters
SAMPLE_URL = (
    "https://krisha.kz/arenda/kvartiry/astana/"
    "?das[_sys.hasphoto]=1"
    "&das[price][from]=40000"
    "&das[price][to]=120000"
    "&das[live.rooms]=2"
    "&bounds=71.41%2C51.16%3B71.49%2C51.20"
)

SAMPLE_HTML = """
<html><body>
<section class="a-list">
  <div class="a-card" data-id="101234567">
    <div class="a-card__header">
      <a href="/a/show/101234567" class="a-card__title">
        2-комнатная квартира, 55 м², 3/9 этаж
      </a>
    </div>
    <div class="a-card__price">80 000 ₸/мес</div>
    <div class="a-card__description">ул. Александра Пушкина, 10</div>
    <div class="a-card__owner">Хозяин</div>
    <meta itemprop="latitude" content="51.1801"/>
    <meta itemprop="longitude" content="71.4460"/>
    <img class="a-card__img" src="https://photos.krisha.kz/photo/1.jpg"/>
  </div>
  <div class="a-card" data-id="101234568">
    <div class="a-card__header">
      <a href="/a/show/101234568" class="a-card__title">
        1-комнатная квартира, 38 м², 5/12 этаж
      </a>
    </div>
    <div class="a-card__price">55 000 ₸/мес</div>
    <div class="a-card__description">просп. Абылай Хана, 5</div>
    <div class="a-card__owner">Агентство</div>
    <meta itemprop="latitude" content="51.1750"/>
    <meta itemprop="longitude" content="71.4380"/>
  </div>
</section>
</body></html>
"""
