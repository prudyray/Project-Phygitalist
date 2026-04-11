"""
Base search view — drives all catalogue search and browse pages.
"""

import logging
from django.views.generic.list import ListView
from django.utils.translation import gettext
from oscar.core.loading import get_model

from shop.apps.search import defaults
from shop.apps.search.facets import process_facets
from shop.apps.search.backend import get_client
from shop.apps.search.queries import (
    build_search_body,
    build_sort,
    build_aggs,
    build_facet_filters,
    build_is_public_filter,
    build_is_available_filter,
    build_price_range_filter,
)

logger = logging.getLogger(__name__)

Product = get_model("catalogue", "Product")


class SearchPaginator:
    """Lightweight paginator backed by Manticore total hit count."""

    def __init__(self, total_count, page_size):
        self.count = total_count
        self.page_size = page_size
        self.num_pages = max(1, -(-total_count // page_size))  # ceiling division

    def get_page(self, page_num):
        try:
            page_num = int(page_num)
        except (TypeError, ValueError):
            page_num = 1
        page_num = max(1, min(page_num, self.num_pages))
        return SearchPage(self, page_num)


class SearchPage:
    """Lightweight page object compatible with Oscar templates."""

    def __init__(self, paginator, number):
        self.paginator = paginator
        self.number = number
        self.object_list = []

    def start_index(self):
        return (self.number - 1) * self.paginator.page_size + 1

    def end_index(self):
        return min(self.number * self.paginator.page_size, self.paginator.count)

    def has_next(self):
        return self.number < self.paginator.num_pages

    def has_previous(self):
        return self.number > 1

    def next_page_number(self):
        return self.number + 1

    def previous_page_number(self):
        return self.number - 1

    def __iter__(self):
        return iter(self.object_list)

    def __len__(self):
        return len(self.object_list)

    def __bool__(self):
        return bool(self.object_list)


class BaseSearchView(ListView):
    model = Product
    paginate_by = defaults.DEFAULT_ITEMS_PER_PAGE
    form_class = None
    aggs_definitions = defaults.FACETS
    context_object_name = "products"

    def get_aggs_definitions(self):
        return self.aggs_definitions

    def get_default_filters(self):
        filters = [build_is_public_filter()]
        if defaults.FILTER_AVAILABLE:
            filters.append(build_is_available_filter())
        return filters

    def get_facet_filters(self):
        return build_facet_filters(
            self.form.selected_multi_facets, self.get_aggs_definitions()
        )

    def get_price_filters(self):
        """Return price range filter clause if the form provides bounds."""
        if not hasattr(self.form, "cleaned_data"):
            return None
        price_min = self.form.cleaned_data.get("price_min")
        price_max = self.form.cleaned_data.get("price_max")
        return build_price_range_filter(price_min, price_max)

    def get_sort_by(self):
        ordering = None
        if self.form.is_valid():
            ordering = self.form.get_sort_params(self.form.cleaned_data)

        if not ordering and not self.request.GET.get("q"):
            ordering = defaults.DEFAULT_ORDERING

        return build_sort(ordering)

    def get_form(self, request):
        return self.form_class(
            data=request.GET or {},
            selected_facets=request.GET.getlist("selected_facets", []),
        )

    def _execute_search(self, q, filters, sort, page_size, offset, aggs):
        """Run the Manticore search query and return the raw response dict."""
        import manticoresearch
        body = build_search_body(q, filters, sort, page_size, offset, aggs)
        body["table"] = defaults.PRODUCTS_TABLE

        search_api = manticoresearch.SearchApi(get_client())
        try:
            response = search_api.search(body)
            # The SDK returns a SearchResponse object; convert to dict
            if hasattr(response, "hits"):
                hits_obj = response.hits
                total = hits_obj.total if hits_obj else 0
                hits = hits_obj.hits if hits_obj else []
                aggs_raw = getattr(response, "aggregations", None) or {}
                return total, hits, {"aggregations": aggs_raw}
        except Exception as exc:
            logger.warning("Manticore search error: %s", exc)
        return 0, [], {"aggregations": {}}

    def _hydrate_products(self, hits):
        """
        Resolve hit IDs to Product ORM objects in a single query,
        preserving the Manticore-scored order.

        Note: HitsHits.id uses StrictInt with alias '_id', but Manticore
        returns _id as a string in JSON. Use to_dict() to get the raw value.
        """
        if not hits:
            return []
        ids = []
        for h in hits:
            try:
                # h.id may be None if Manticore returned "_id" as a string
                # (StrictInt won't coerce). Fall back to the aliased dict.
                raw_id = h.id
                if raw_id is None:
                    raw_id = h.to_dict().get("_id")
                if raw_id is not None:
                    ids.append(int(raw_id))
            except (AttributeError, TypeError, ValueError):
                pass
        if not ids:
            return []
        bulk = Product.objects.in_bulk(ids)
        return [bulk[pk] for pk in ids if pk in bulk]

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        self.form = self.get_form(self.request)
        self.form.is_valid()

        page_num = int(self.request.GET.get("page", 1))
        page_size = self.paginate_by
        offset = (page_num - 1) * page_size

        q = self.request.GET.get("q", "")

        if q:
            from shop.apps.search.signals import query_hit
            query_hit.send(sender=self, querystring=q)

        # Combine all filters
        filters = self.get_default_filters() + self.get_facet_filters()
        price_filter = self.get_price_filters()
        if price_filter:
            filters.append(price_filter)

        sort = self.get_sort_by()
        aggs_defs = self.get_aggs_definitions()
        aggs = build_aggs(aggs_defs)

        # Run filtered search (for actual results)
        total, hits, filtered_result = self._execute_search(
            q, filters, sort, page_size, offset, aggs
        )

        products = self._hydrate_products(hits)

        # Run unfiltered search (for full facet counts)
        unfiltered_result = filtered_result  # default: same result
        if aggs_defs and self.form.selected_multi_facets:
            base_filters = self.get_default_filters()
            price_filter = self.get_price_filters()
            if price_filter:
                base_filters.append(price_filter)
            _, _, unfiltered_result = self._execute_search(
                q, base_filters, sort, 0, 0, aggs
            )

        # Facet post-processing
        processed_facets = None
        if aggs_defs and unfiltered_result.get("aggregations"):
            processed_facets = process_facets(
                self.request.get_full_path(),
                self.form,
                (unfiltered_result, filtered_result),
                facet_definitions=aggs_defs,
            )

        paginator = SearchPaginator(total, page_size)
        page_obj = paginator.get_page(page_num)
        page_obj.object_list = products

        context["paginator"] = paginator
        context["page_obj"] = page_obj
        context["page"] = page_obj
        context[self.context_object_name] = products
        context["facet_data"] = processed_facets
        context["has_facets"] = bool(processed_facets)
        context["query"] = q or gettext("Blank")
        context["form"] = self.form
        context["search_form"] = self.form
        context["selected_facets"] = self.request.GET.getlist("selected_facets", [])

        return context

    # ListView requires get_queryset but we don't use the DB queryset
    def get_queryset(self):
        return Product.objects.none()
