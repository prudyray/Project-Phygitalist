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

    Returns {"results": ["suggestion1", "suggestion2", ...]}

    Strategy:
    1. Try Manticore CALL SUGGEST for spell-corrected prefix suggestions.
    2. Fall back to a prefix query_string match on the title field.
    """

    MAX_RESULTS = 8

    def get(self, request):
        q = request.GET.get("q", "").strip()
        if len(q) < 3:
            return JsonResponse({"results": []})

        suggestions = self._call_suggest(q)
        if not suggestions:
            suggestions = self._prefix_search(q)

        return JsonResponse({"results": suggestions[:self.MAX_RESULTS]})

    def _call_suggest(self, q):
        """Use Manticore CALL SUGGEST for fuzzy/spell-corrected suggestions."""
        try:
            import manticoresearch
            utils_api = manticoresearch.UtilsApi(get_client())
            # CALL SUGGEST returns rows with 'suggest' column
            resp = utils_api.sql(
                f"CALL SUGGEST('{_escape_sql(q)}', '{defaults.PRODUCTS_TABLE}')"
            )
            results = []
            if resp and hasattr(resp, "__iter__"):
                for row in resp:
                    # resp may be a list of dicts or objects
                    if isinstance(row, dict):
                        s = row.get("suggest") or row.get("word")
                    else:
                        s = getattr(row, "suggest", None) or getattr(row, "word", None)
                    if s and s.lower() != q.lower():
                        results.append(str(s))
            return results
        except Exception as exc:
            logger.debug("CALL SUGGEST failed for %r: %s", q, exc)
            return []

    def _prefix_search(self, q):
        """Fall back to a prefix match on title using the JSON search API."""
        try:
            import manticoresearch
            search_api = manticoresearch.SearchApi(get_client())
            body = {
                "table": defaults.PRODUCTS_TABLE,
                "query": {"query_string": f"{_escape_qs(q)}*"},
                "limit": self.MAX_RESULTS,
                "_source": ["title"],
                "sort": [{"_score": {"order": "desc"}}],
            }
            response = search_api.search(body)
            seen = set()
            results = []
            if response and hasattr(response, "hits") and response.hits:
                for h in (response.hits.hits or []):
                    source = getattr(h, "source", None) or {}
                    title = source.get("title", "") if isinstance(source, dict) else getattr(source, "title", "")
                    if title and title not in seen:
                        seen.add(title)
                        results.append(title)
            return results
        except Exception as exc:
            logger.debug("Prefix search failed for %r: %s", q, exc)
            return []


def _escape_sql(s):
    """Minimal escape for values interpolated into CALL SUGGEST SQL."""
    return s.replace("'", "\\'").replace("\\", "\\\\")


def _escape_qs(s):
    """Strip characters that break Manticore query_string syntax."""
    # Remove common special chars that would cause parse errors
    for ch in r'\/*~@!^$()[]{}':
        s = s.replace(ch, " ")
    return s.strip()


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
