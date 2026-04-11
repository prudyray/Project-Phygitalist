"""
Package re-exports so Oscar's get_class("search.views", "ClassName") works.
"""

from shop.apps.search.views.base import BaseSearchView
from shop.apps.search.views.catalogue import CatalogueView, ProductCategoryView
from shop.apps.search.views.search import SearchView, FacetedSearchView, AutoCompleteView

__all__ = [
    "BaseSearchView",
    "CatalogueView",
    "ProductCategoryView",
    "SearchView",
    "FacetedSearchView",
    "AutoCompleteView",
]
