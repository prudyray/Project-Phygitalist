"""
Direct search view (the /search/ endpoint) and autocomplete.
"""

import logging
from django.http import JsonResponse
from django.views import View

from shop.apps.search.views.base import BaseSearchView
from shop.apps.search.forms import SearchForm
from shop.apps.search import defaults
from shop.apps.search.backend import get_client

logger = logging.getLogger(__name__)


class AutoCompleteView(View):
    """
    GET /search/autocomplete/?q=<prefix>

    Returns {"results": ["Product Title 1", ...]}

    Uses a Manticore SQL SELECT with a prefix MATCH query against the products
    table. The table has min_prefix_len='2' so prefix queries work for 3+ chars.
    """

    MAX_RESULTS = 8

    def get(self, request):
        q = request.GET.get("q", "").strip()
        if len(q) < 3:
            return JsonResponse({"results": []})

        suggestions = self._prefix_search(q)
        return JsonResponse({"results": suggestions})

    def _prefix_search(self, q):
        """
        Prefix match via SearchApi, then fetch titles from the ORM.
        Uses the same ID extraction as _hydrate_products so we know it works.
        """
        from oscar.core.loading import get_model
        Product = get_model("catalogue", "Product")

        try:
            import manticoresearch
            search_api = manticoresearch.SearchApi(get_client())
            safe_q = _escape_sql(q)
            body = {
                "table": defaults.PRODUCTS_TABLE,
                "query": {
                    "bool": {
                        "must": [{"query_string": f"{safe_q}*"}],
                        "filter": [{"equals": {"is_public": 1}}],
                    }
                },
                "limit": self.MAX_RESULTS,
                "sort": [{"_score": {"order": "desc"}}],
            }
            response = search_api.search(body)

            ids = []
            if response and hasattr(response, "hits") and response.hits:
                for h in (response.hits.hits or []):
                    raw_id = h.id
                    if raw_id is None:
                        raw_id = h.to_dict().get("_id")
                    if raw_id is not None:
                        try:
                            ids.append(int(raw_id))
                        except (ValueError, TypeError):
                            pass

            if not ids:
                return []

            bulk = Product.objects.filter(pk__in=ids).in_bulk()
            seen = set()
            results = []
            for pk in ids:
                product = bulk.get(pk)
                if product and product.title and product.title not in seen:
                    seen.add(product.title)
                    results.append(product.title)
            return results

        except Exception as exc:
            logger.warning("Autocomplete prefix search failed for %r: %s", q, exc)
            return []


def _escape_sql(s):
    """Minimal escape for values interpolated into CALL SUGGEST SQL."""
    return s.replace("'", "\\'").replace("\\", "\\\\")



class SearchView(BaseSearchView):
    """Handles the main site-wide /search/?q=... page."""

    form_class = SearchForm
    template_name = "oscar/search/results.html"
    context_object_name = "products"

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx["summary"] = self.request.GET.get("q", "")
        return ctx


# Alias — Oscar's apps.py may look for FacetedSearchView
FacetedSearchView = SearchView
