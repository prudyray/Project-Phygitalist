"""
Manticore Search query builder.

Uses the Manticore JSON HTTP API (via SearchApi) for the main search/filter
query and aggregations. SQL is reserved for DDL, CALL SUGGEST, FACET ranges
(Phase 2).
"""

from decimal import Decimal

from shop.apps.search import defaults


# ---------------------------------------------------------------------------
# Sort helpers
# ---------------------------------------------------------------------------

def build_sort(ordering):
    """
    Convert an ordering string like '-price' or 'title' into a Manticore
    sort clause list.

    Returns a list: e.g. [{"price": {"order": "desc"}}] or ["_score"].
    """
    if not ordering:
        return ["_score"]

    if ordering.startswith("-"):
        field = ordering[1:]
        return [{field: {"order": "desc"}}]

    return [{ordering: {"order": "asc"}}]


# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------

def build_is_public_filter():
    return {"equals": {"is_public": 1}}


def build_is_available_filter():
    return {"equals": {"is_available": 1}}


def build_category_filter(category_ids):
    """Filter by list of category IDs (multi field)."""
    return {"in": {"any(categories)": list(category_ids)}}


def build_price_range_filter(price_min=None, price_max=None):
    """Build a price range filter. Returns None if neither bound is set."""
    if price_min is None and price_max is None:
        return None
    rng = {}
    if price_min is not None:
        rng["gte"] = float(price_min)
    if price_max is not None:
        rng["lte"] = float(price_max)
    return {"range": {"price": rng}}


# ---------------------------------------------------------------------------
# Facet filter helpers
# ---------------------------------------------------------------------------

def build_facet_filters(selected_multi_facets, aggs_definitions):
    """
    Convert ``form.selected_multi_facets`` into Manticore bool filter clauses.

    selected_multi_facets: dict  { facet_name: [value, ...] }
    aggs_definitions: list of facet definition dicts (from OSCAR_SEARCH_FACETS)
    """
    filters = []
    definition_map = {d["name"]: d for d in (aggs_definitions or [])}

    for name, values in selected_multi_facets.items():
        if not values:
            continue
        defn = definition_map.get(name)
        if defn is None:
            continue

        if defn.get("type") == "range":
            ranges = []
            for val in values:
                if val.startswith("*-"):
                    ranges.append({"range": {name: {"lte": float(Decimal(val[2:]))}}})
                elif val.endswith("-*"):
                    ranges.append({"range": {name: {"gte": float(Decimal(val[:-2]))}}})
                else:
                    from_, to = val.split("-", 1)
                    ranges.append(
                        {"range": {name: {"gte": float(Decimal(from_)), "lte": float(Decimal(to))}}}
                    )
            if len(ranges) == 1:
                filters.append(ranges[0])
            elif ranges:
                filters.append({"bool": {"should": ranges}})
        else:
            # term / multi facet — use "in" for multi fields, "equals" for single
            filters.append({"in": {name: values}})

    return filters


# ---------------------------------------------------------------------------
# Aggregation builders
# ---------------------------------------------------------------------------

def build_aggs(aggs_definitions):
    """
    Build Manticore JSON aggs dict from facet definitions.

    Supports:
    - type="term"  -> terms aggregation
    - type="range" -> range aggregation
    """
    if not aggs_definitions:
        return {}

    aggs = {}
    bucket_size = defaults.FACET_BUCKET_SIZE

    for defn in aggs_definitions:
        name = defn["name"]
        facet_type = defn.get("type", "term")

        if facet_type == "range":
            ranges = defn.get("ranges", [])
            aggs[name] = {"range": {"field": name, "ranges": ranges}}
        else:
            aggs[name] = {"terms": {"field": name, "size": bucket_size}}

    return aggs


# ---------------------------------------------------------------------------
# Main search body builder
# ---------------------------------------------------------------------------

def build_search_body(
    q,
    filters,
    sort,
    size,
    offset,
    aggs=None,
):
    """
    Build the full Manticore JSON search request body.

    q: query string (may be empty)
    filters: list of Manticore filter dicts
    sort: list (from build_sort)
    size: int (page size)
    offset: int (pagination offset)
    aggs: dict (from build_aggs)
    """
    # Build the query clause
    if q:
        query_clause = {"query_string": q}
    else:
        query_clause = {"match_all": {}}

    if filters:
        query = {
            "bool": {
                "must": query_clause,
                "filter": filters,
            }
        }
    else:
        query = query_clause

    body = {
        "query": query,
        "limit": size,
        "offset": offset,
        "sort": sort,
        "track_scores": True,
    }

    if aggs:
        body["aggs"] = aggs

    return body
