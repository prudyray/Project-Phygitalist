"""
Direct search view (the /search/ endpoint).
"""

from shop.apps.search.views.base import BaseSearchView
from shop.apps.search.forms import SearchForm


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
