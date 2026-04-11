"""
Manticore Search indexer — defines table schemas and document builders
for products and categories.

Uses:
  - UtilsApi.sql() for DDL
  - IndexApi.replace() for single-document upserts
  - IndexApi.bulk() for batch upserts
  - IndexApi.delete() for document removal
"""

import json
import logging
from django.utils.html import strip_tags

from shop.apps.search import defaults
from shop.apps.search.backend import get_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table schemas
# ---------------------------------------------------------------------------

_PRODUCTS_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS {table}(
    title text,
    search_title text,
    description text,
    upc string,
    slug string,
    absolute_url string,
    product_class string,
    structure string,
    parent_id integer,
    is_public bool,
    is_available bool,
    num_available integer,
    price float,
    currency string,
    rating float,
    priority integer,
    popularity integer,
    date_created integer,
    date_updated integer,
    categories multi,
    category_full_names text,
    string_attrs text
) morphology='stem_en' min_prefix_len='2' min_infix_len='2' html_strip='1'
""".strip()

_CATEGORIES_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS {table}(
    title text,
    search_title text,
    full_name text,
    full_slug string,
    code string,
    description text,
    absolute_url string,
    is_public bool
)
""".strip()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunked(iterable, size):
    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _get_utils_api():
    import manticoresearch
    return manticoresearch.UtilsApi(get_client())


def _get_index_api():
    import manticoresearch
    return manticoresearch.IndexApi(get_client())


# ---------------------------------------------------------------------------
# Base index
# ---------------------------------------------------------------------------

class BaseManticoreIndex:
    """Abstract base — subclasses set TABLE_NAME, CREATE_SQL, and override
    make_document(obj) + get_queryset()."""

    TABLE_NAME = None
    CREATE_SQL = None

    def ensure_schema(self):
        utils_api = _get_utils_api()
        sql = self.CREATE_SQL.format(table=self.TABLE_NAME)
        try:
            utils_api.sql(sql)
        except Exception as exc:
            logger.warning("ensure_schema error for %s: %s", self.TABLE_NAME, exc)

    def replace(self, obj_id, doc):
        """Insert or replace a single document."""
        import manticoresearch
        index_api = _get_index_api()
        req = manticoresearch.InsertDocumentRequest(
            table=self.TABLE_NAME, id=obj_id, doc=doc
        )
        index_api.replace(req)

    def bulk_replace(self, id_doc_pairs):
        """Bulk upsert a list of (id, doc) tuples via NDJSON."""
        if not id_doc_pairs:
            return
        index_api = _get_index_api()
        lines = [
            json.dumps({"replace": {"table": self.TABLE_NAME, "id": doc_id, "doc": doc}})
            for doc_id, doc in id_doc_pairs
        ]
        index_api.bulk("\n".join(lines))

    def delete(self, obj_id):
        """Delete a document by ID."""
        import manticoresearch
        index_api = _get_index_api()
        req = manticoresearch.DeleteDocumentRequest(table=self.TABLE_NAME, id=obj_id)
        index_api.delete(req)

    def reindex(self, queryset, chunk_size=None):
        """Full reindex: ensure schema, truncate, bulk insert all documents."""
        if chunk_size is None:
            chunk_size = defaults.INDEXING_CHUNK_SIZE

        self.ensure_schema()

        utils_api = _get_utils_api()
        try:
            utils_api.sql(f"TRUNCATE TABLE {self.TABLE_NAME}")
        except Exception as exc:
            logger.warning("TRUNCATE failed for %s: %s", self.TABLE_NAME, exc)

        total = 0
        for chunk in _chunked(queryset.iterator(chunk_size=chunk_size), chunk_size):
            pairs = []
            for obj in chunk:
                try:
                    doc = self.make_document(obj)
                    pairs.append((obj.id, doc))
                except Exception as exc:
                    logger.warning(
                        "Failed to build document for %s id=%s: %s",
                        self.TABLE_NAME, obj.id, exc,
                    )
            if pairs:
                self.bulk_replace(pairs)
                total += len(pairs)

        logger.info("Reindexed %d documents into %s", total, self.TABLE_NAME)
        return total

    def make_document(self, obj):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Product index
# ---------------------------------------------------------------------------

def _get_product_price_and_stock(product):
    """
    Return (price_float, currency_str, num_available_int, is_available_bool).

    For PARENT products we look at the cheapest child's stockrecord.
    For STANDALONE / CHILD we use the product's own stockrecords.
    """
    from oscar.core.loading import get_model
    StockRecord = get_model("partner", "StockRecord")

    if product.structure == "parent":
        qs = StockRecord.objects.filter(product__parent=product)
    else:
        qs = product.stockrecords.all()

    sr = qs.order_by("price").first()
    if sr is None:
        return 0.0, "", 0, False

    price = float(sr.price) if sr.price else 0.0
    currency = sr.price_currency or ""
    net = max(0, (sr.num_in_stock or 0) - (sr.num_allocated or 0))
    return price, currency, net, net > 0


def _get_string_attrs(product):
    """Collect all text-like attribute values into a single string."""
    texts = []
    for av in product.attribute_values.select_related("attribute").all():
        if av.attribute.type in ("file", "image"):
            continue
        try:
            val = str(av.value_as_text)
            if val:
                texts.append(val)
        except Exception:
            pass

    # For parent products, also include children's titles + attrs
    if product.structure == "parent":
        for child in product.children.prefetch_related(
            "attribute_values__attribute"
        ).all():
            texts.append(child.title)
            for av in child.attribute_values.select_related("attribute").all():
                if av.attribute.type in ("file", "image"):
                    continue
                try:
                    val = str(av.value_as_text)
                    if val:
                        texts.append(val)
                except Exception:
                    pass

    return " ".join(texts)


def _get_category_ids_and_names(product):
    """
    Return (list_of_category_ids, space_joined_full_names).
    Returns direct categories only — at query time we expand to descendants.
    """
    categories = list(product.categories.all())
    ids = [c.id for c in categories]
    names = " ".join(c.full_name for c in categories)
    return ids, names


def _ts(dt):
    """Convert a datetime to a Unix timestamp int, or 0 if None."""
    if dt is None:
        return 0
    try:
        return int(dt.timestamp())
    except Exception:
        return 0


class ProductManticoreIndex(BaseManticoreIndex):
    TABLE_NAME = defaults.PRODUCTS_TABLE
    CREATE_SQL = _PRODUCTS_CREATE_SQL

    def make_document(self, product):
        price, currency, num_available, is_available = _get_product_price_and_stock(
            product
        )
        category_ids, category_full_names = _get_category_ids_and_names(product)
        string_attrs = _get_string_attrs(product)

        if not is_available and defaults.PRIORITIZE_AVAILABLE_PRODUCTS:
            priority = -1
        else:
            priority = 0

        description = ""
        if product.description:
            description = strip_tags(product.description)

        parent_id = product.parent_id if product.parent_id else 0

        return {
            "title": product.title or "",
            "search_title": product.title or "",
            "description": description,
            "upc": product.upc or "",
            "slug": product.slug or "",
            "absolute_url": product.get_absolute_url() or "",
            "product_class": (
                product.product_class.slug if product.product_class else ""
            ),
            "structure": product.structure or "",
            "parent_id": parent_id,
            "is_public": int(bool(product.is_public)),
            "is_available": int(is_available),
            "num_available": num_available,
            "price": price,
            "currency": currency,
            "rating": float(product.rating) if product.rating else 0.0,
            "priority": priority,
            "popularity": getattr(product, "popularity", 0) or 0,
            "date_created": _ts(product.date_created),
            "date_updated": _ts(product.date_updated),
            "categories": category_ids,
            "category_full_names": category_full_names,
            "string_attrs": string_attrs,
        }

    def get_queryset(self):
        from oscar.core.loading import get_model
        Product = get_model("catalogue", "Product")
        return (
            Product.objects.browsable()
            .select_related("product_class", "parent")
            .prefetch_related(
                "categories",
                "stockrecords",
                "attribute_values__attribute",
                "children__stockrecords",
                "children__attribute_values__attribute",
            )
        )


# ---------------------------------------------------------------------------
# Category index
# ---------------------------------------------------------------------------

class CategoryManticoreIndex(BaseManticoreIndex):
    TABLE_NAME = defaults.CATEGORIES_TABLE
    CREATE_SQL = _CATEGORIES_CREATE_SQL

    def make_document(self, category):
        return {
            "title": category.name or "",
            "search_title": category.name or "",
            "full_name": category.full_name or "",
            "full_slug": category.full_slug or "",
            "code": category.slug or "",
            "description": (
                strip_tags(category.description) if category.description else ""
            ),
            "absolute_url": category.get_absolute_url() or "",
            "is_public": int(bool(category.is_public)),
        }

    def get_queryset(self):
        from oscar.core.loading import get_model
        Category = get_model("catalogue", "Category")
        return Category.objects.browsable()
