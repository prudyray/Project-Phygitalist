"""
Facet post-processing — converts Manticore aggregation buckets into
template-friendly Facet / FacetBucketItem objects.

Ported from oscar_elasticsearch.search.facets with purl replaced by urllib.
"""

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from django.utils.module_loading import import_string
from django.utils.translation import gettext

from shop.apps.search import defaults


# ---------------------------------------------------------------------------
# URL helpers (replaces purl)
# ---------------------------------------------------------------------------

def _remove_query_param(url_str, key, value=None):
    """Remove a query parameter (optionally a specific value) from a URL string."""
    parts = urlparse(url_str)
    params = parse_qs(parts.query, keep_blank_values=True)
    if key in params:
        if value is not None:
            params[key] = [v for v in params[key] if v != value]
            if not params[key]:
                del params[key]
        else:
            del params[key]
    query = urlencode(params, doseq=True)
    return urlunparse(parts._replace(query=query))


def _append_query_param(url_str, key, value):
    """Append a query parameter (preserving existing values) to a URL string."""
    parts = urlparse(url_str)
    params = parse_qs(parts.query, keep_blank_values=True)
    params.setdefault(key, []).append(value)
    query = urlencode(params, doseq=True)
    return urlunparse(parts._replace(query=query))


def strip_pagination(url_str):
    if "page" in url_str:
        url_str = _remove_query_param(url_str, "page")
    return url_str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def bucket_key(bucket):
    if "key_as_string" in bucket:
        return bucket["key_as_string"]
    return bucket["key"]


def bucket_to_lookup(buckets):
    return {bucket_key(item): item["doc_count"] for item in buckets}


def process_facets(request_full_path, form, facets, facet_definitions=None):
    unfiltered_facets, filtered_facets = facets
    selected_multi_facets = form.selected_multi_facets
    if not facet_definitions:
        facet_definitions = []
    processed_facets = {}

    for facet_definition in facet_definitions:
        facet_name = facet_definition["name"]
        selected_facets = selected_multi_facets[facet_name]
        unfiltered_facet = unfiltered_facets.get("aggregations", {}).get(facet_name)
        filtered_facet = filtered_facets.get("aggregations", {}).get(facet_name, {})
        if unfiltered_facet is None:
            continue

        unfiltered_buckets = unfiltered_facet.get("buckets", [])
        filtered_buckets = filtered_facet.get("buckets", [])

        if len(unfiltered_buckets) < defaults.MIN_NUM_BUCKETS:
            continue

        if facet_definition.get("type") == "range" and not any(
            bucket.get("doc_count", 0) > 0 for bucket in unfiltered_buckets
        ):
            continue

        if facet_definition.get("type") == "date_histogram":
            unfiltered_buckets = [b for b in unfiltered_buckets if b["doc_count"] > 0]
            filtered_buckets = [b for b in filtered_buckets if b["doc_count"] > 0]

        facet = Facet(
            facet_definition,
            unfiltered_buckets,
            filtered_buckets,
            request_full_path,
            selected_facets,
        )
        processed_facets[facet_name] = facet

    return processed_facets


class Facet:
    def __init__(
        self,
        facet_definition,
        unfiltered_buckets,
        filtered_buckets,
        request_url,
        selected_facets=None,
    ):
        self.facet = facet_definition["name"]
        self.label = facet_definition["label"]
        self.typ = facet_definition["type"]
        self.unfiltered_buckets = unfiltered_buckets
        self.filtered_buckets = filtered_buckets
        self.request_url = request_url
        self.selected_facets = set(selected_facets or [])
        self.formatter = None
        formatter = (facet_definition.get("formatter") or "").strip()
        if formatter:
            self.formatter = import_string(formatter)

    def name(self):
        return gettext(str(self.label or ""))

    def has_selection(self):
        return bool(self.selected_facets)

    def results(self):
        lookup = bucket_to_lookup(self.filtered_buckets)
        max_bucket_count = max(lookup.values()) if lookup else 0

        for bucket in self.unfiltered_buckets:
            key = bucket_key(bucket)

            selected = str(key) in self.selected_facets

            if self.has_selection() and not selected:
                doc_count = min(
                    lookup.get(key, 0) or max_bucket_count, bucket["doc_count"]
                )
            else:
                doc_count = lookup.get(key, 0)

            yield FacetBucketItem(
                self.facet, key, doc_count, self.request_url, selected, self.formatter
            )


class FacetBucketItem:
    def __init__(self, facet, key, doc_count, request_url, selected, formatter=None):
        self.facet = facet
        self.key = key
        self.doc_count = doc_count
        self.request_url = request_url
        self.selected = selected
        self.show_count = True
        self.formatter = formatter

    def name(self):
        return self.key

    def __str__(self):
        if self.formatter is not None:
            return f"{self.formatter(self.key)!s}"
        return f"{self.key!s}"

    def select_url(self):
        url = _append_query_param(
            self.request_url, "selected_facets", "%s:%s" % (self.facet, self.key)
        )
        return strip_pagination(url)

    def deselect_url(self):
        url = _remove_query_param(
            self.request_url, "selected_facets", "%s:%s" % (self.facet, self.key)
        )
        return strip_pagination(url)
