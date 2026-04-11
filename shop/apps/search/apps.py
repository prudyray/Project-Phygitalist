from oscar.core.application import OscarConfig
from django.urls import path
from django.utils.translation import gettext_lazy as _


class SearchConfig(OscarConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shop.apps.search"
    label = "search"
    namespace = "search"
    verbose_name = _("Catalog Search")

    def ready(self):
        super().ready()
        from shop.apps.search.views import SearchView, CatalogueView, ProductCategoryView

        self.search_view = SearchView
        self.catalogue_view = CatalogueView
        self.category_view = ProductCategoryView

    def get_urls(self):
        urls = [
            path("", self.search_view.as_view(), name="search"),
        ]
        return self.post_process_urls(urls)
