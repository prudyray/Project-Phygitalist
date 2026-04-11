"""
Catalogue browse views backed by Manticore Search.
"""

from django.contrib import messages
from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _
from urllib.parse import quote

from oscar.core.loading import get_model

from shop.apps.search.views.base import BaseSearchView
from shop.apps.search.forms import BrowseCategoryForm, CategoryForm
from shop.apps.search.queries import build_category_filter

Category = get_model("catalogue", "Category")


class CatalogueView(BaseSearchView):
    """Browse all products in the catalogue."""

    form_class = BrowseCategoryForm
    context_object_name = "products"
    template_name = "oscar/catalogue/browse.html"
    enforce_paths = True

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except Http404:
            messages.error(request, _("The given page number was invalid."))
            return redirect("catalogue:index")

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx["summary"] = _("All products")
        return ctx


class ProductCategoryView(BaseSearchView):
    """Browse products in a given category (including all descendants)."""

    form_class = CategoryForm
    enforce_paths = True
    context_object_name = "products"
    template_name = "oscar/catalogue/category.html"

    def get(self, request, *args, **kwargs):
        self.category = self.get_category()

        if not self.is_viewable(self.category, request):
            raise Http404()

        potential_redirect = self.redirect_if_necessary(request.path, self.category)
        if potential_redirect is not None:
            return potential_redirect

        try:
            return super().get(request, *args, **kwargs)
        except Http404:
            messages.error(request, _("The given page number was invalid."))
            return redirect(self.category.get_absolute_url())

    def is_viewable(self, category, request):
        return category.is_public or request.user.is_staff

    def redirect_if_necessary(self, current_path, category):
        if self.enforce_paths:
            expected_path = category.get_absolute_url()
            if expected_path != quote(current_path):
                return HttpResponsePermanentRedirect(expected_path)

    def get_category(self):
        return get_object_or_404(Category, pk=self.kwargs["pk"])

    def get_default_filters(self):
        filters = super().get_default_filters()
        category_ids = list(
            self.category.get_descendants_and_self().values_list("pk", flat=True)
        )
        filters.append(build_category_filter(category_ids))
        return filters

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category"] = self.category
        return context
