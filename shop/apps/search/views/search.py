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
        """SELECT titles from Manticore matching the prefix."""
        try:
            import manticoresearch
            utils_api = manticoresearch.UtilsApi(get_client())
            safe_q = _escape_sql(q)
            sql = (
                f"SELECT title FROM {defaults.PRODUCTS_TABLE} "
                f"WHERE MATCH('{safe_q}*') AND is_public=1 "
                f"LIMIT {self.MAX_RESULTS}"
            )
            resp = utils_api.sql(sql)
            # resp is a list of result-set objects; each has a .data attr
            # containing a list of row dicts like {"title": "..."}
            results = []
            seen = set()
            for result_set in (resp or []):
                if isinstance(result_set, dict):
                    rows = result_set.get("data") or []
                else:
                    rows = getattr(result_set, "data", None) or []
                for row in rows:
                    title = row.get("title") if isinstance(row, dict) else getattr(row, "title", None)
                    if title and title not in seen:
                        seen.add(title)
                        results.append(title)
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
