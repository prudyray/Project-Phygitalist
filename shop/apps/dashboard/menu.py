from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from shop.apps.dashboard.nav import Node


def get_nodes(user):
    all_nodes = create_menu(settings.OSCAR_DASHBOARD_NAVIGATION)
    visible_nodes = []
    for node in all_nodes:
        filtered_node = node.filter(user)
        if filtered_node and (
            filtered_node.has_children() or not filtered_node.is_heading
        ):
            visible_nodes.append(filtered_node)
    return visible_nodes


def staff_access_fn(user, url_name, url_args=None, url_kwargs=None):
    """Access function for non-dashboard URLs — bypasses OscarDashboardConfig lookup."""
    return user.is_staff

def superuser_access_fn(user, url_name, url_args=None, url_kwargs=None):
    return user.is_superuser

def _resolve_access_fn(value, default):
    if value is None:
        return default
    return import_string(value) if isinstance(value, str) else value


def create_menu(menu_items, parent=None):
    nodes = []
    default_fn = import_string(settings.OSCAR_DASHBOARD_DEFAULT_ACCESS_FUNCTION)
    for menu_dict in menu_items:
        try:
            label = menu_dict["label"]
        except KeyError:
            raise ImproperlyConfigured("No label specified for menu item in dashboard")

        access_fn = _resolve_access_fn(menu_dict.get("access_fn"), default_fn)
        children = menu_dict.get("children", [])
        if children:
            node = Node(
                label=label,
                icon=menu_dict.get("icon", None),
                access_fn=access_fn,
                active=menu_dict.get("active", None),
            )
            create_menu(children, parent=node)
        else:
            node = Node(
                label=label,
                icon=menu_dict.get("icon", None),
                url_name=menu_dict.get("url_name", None),
                url_kwargs=menu_dict.get("url_kwargs", None),
                url_args=menu_dict.get("url_args", None),
                access_fn=access_fn,
                active=menu_dict.get("active", None),
            )
        if parent is None:
            nodes.append(node)
        else:
            parent.add_child(node)
    return nodes
