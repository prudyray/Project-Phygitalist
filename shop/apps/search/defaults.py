"""
Default settings for shop.apps.search.
All values can be overridden via OSCAR_SEARCH_* keys in Django settings.
"""

from django.conf import settings
from django.utils.translation import gettext_lazy as _

MANTICORE_URL = getattr(settings, "MANTICORE_URL", "http://127.0.0.1:9308")

PRODUCTS_TABLE = getattr(settings, "OSCAR_SEARCH_PRODUCTS_TABLE", "products")
CATEGORIES_TABLE = getattr(settings, "OSCAR_SEARCH_CATEGORIES_TABLE", "categories")

INDEXING_CHUNK_SIZE = getattr(settings, "OSCAR_SEARCH_INDEXING_CHUNK_SIZE", 400)
MONTHS_TO_RUN_ANALYTICS = getattr(settings, "OSCAR_SEARCH_MONTHS_TO_RUN_ANALYTICS", 3)

DEFAULT_ITEMS_PER_PAGE = getattr(
    settings,
    "OSCAR_SEARCH_DEFAULT_ITEMS_PER_PAGE",
    settings.OSCAR_PRODUCTS_PER_PAGE,
)
ITEMS_PER_PAGE_CHOICES = getattr(
    settings, "OSCAR_SEARCH_ITEMS_PER_PAGE_CHOICES", [DEFAULT_ITEMS_PER_PAGE]
)

FACETS = getattr(settings, "MANTICORE_FACETS", [])
FACET_BUCKET_SIZE = getattr(settings, "OSCAR_SEARCH_FACET_BUCKET_SIZE", 10)
MIN_NUM_BUCKETS = getattr(settings, "OSCAR_SEARCH_MIN_NUM_BUCKETS", 2)

FILTER_AVAILABLE = getattr(settings, "OSCAR_SEARCH_FILTER_AVAILABLE", False)
PRIORITIZE_AVAILABLE_PRODUCTS = getattr(
    settings, "OSCAR_SEARCH_PRIORITIZE_AVAILABLE_PRODUCTS", True
)
HANDLE_STOCKRECORD_CHANGES = getattr(
    settings, "OSCAR_SEARCH_HANDLE_STOCKRECORD_CHANGES", True
)

RELEVANCY = "relevancy"
TOP_RATED = "rating"
NEWEST = "newest"
PRICE_HIGH_TO_LOW = "price-desc"
PRICE_LOW_TO_HIGH = "price-asc"
TITLE_A_TO_Z = "title-asc"
TITLE_Z_TO_A = "title-desc"
POPULARITY = "popularity"

SORT_BY_CHOICES_SEARCH = getattr(
    settings,
    "OSCAR_SEARCH_SORT_BY_CHOICES_SEARCH",
    [
        (RELEVANCY, _("Relevancy")),
        (POPULARITY, _("Most popular")),
        (NEWEST, _("Newest")),
    ],
)

SORT_BY_MAP_SEARCH = getattr(
    settings,
    "OSCAR_SEARCH_SORT_BY_MAP_SEARCH",
    {NEWEST: "-date_created", POPULARITY: "-popularity"},
)

SORT_BY_CHOICES_CATALOGUE = getattr(
    settings,
    "OSCAR_SEARCH_SORT_BY_CHOICES_CATALOGUE",
    [
        (RELEVANCY, _("Relevancy")),
        (POPULARITY, _("Most popular")),
        (TOP_RATED, _("Customer rating")),
        (NEWEST, _("Newest")),
        (PRICE_HIGH_TO_LOW, _("Price high to low")),
        (PRICE_LOW_TO_HIGH, _("Price low to high")),
        (TITLE_A_TO_Z, _("Title A to Z")),
        (TITLE_Z_TO_A, _("Title Z to A")),
    ],
)

SORT_BY_MAP_CATALOGUE = getattr(
    settings,
    "OSCAR_SEARCH_SORT_BY_MAP_CATALOGUE",
    {
        TOP_RATED: "-rating",
        NEWEST: "-date_created",
        POPULARITY: "-popularity",
        PRICE_HIGH_TO_LOW: "-price",
        PRICE_LOW_TO_HIGH: "price",
        TITLE_A_TO_Z: "title",
        TITLE_Z_TO_A: "-title",
    },
)

DEFAULT_ORDERING = getattr(settings, "OSCAR_SEARCH_DEFAULT_ORDERING", None)
