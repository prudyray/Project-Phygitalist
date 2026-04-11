"""
Manticore Search client singleton.
"""

import manticoresearch
from shop.apps.search import defaults


def _make_configuration():
    return manticoresearch.Configuration(host=defaults.MANTICORE_URL)


_configuration = None


def get_configuration():
    global _configuration
    if _configuration is None:
        _configuration = _make_configuration()
    return _configuration


def get_client():
    return manticoresearch.ApiClient(get_configuration())


def get_index_api():
    return manticoresearch.IndexApi(get_client())


def get_search_api():
    return manticoresearch.SearchApi(get_client())


def get_utils_api():
    return manticoresearch.UtilsApi(get_client())
