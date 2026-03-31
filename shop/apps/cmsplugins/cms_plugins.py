from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from django.utils.translation import gettext as _
from shop.apps.cmsplugins.models import FeaturedProduct, FeaturedProductCollection, GroupBuyProduct, AdaCollabProduct, GiftsProduct
from . import forms

@plugin_pool.register_plugin
class FeaturedProductCollectionPlugin(CMSPluginBase):
    model = FeaturedProductCollection
    module = _("Zite69")
    name = _("Featured Product Collection")
    render_template = "cmsplugins/featured_collection.html"
    allow_children = True
    child_classes = ["FeaturedProductPlugin"]

    def render(self, context, instance, placeholder):
        context.update({"instance": instance})
        return context

@plugin_pool.register_plugin
class FeaturedProductPlugin(CMSPluginBase):
    model = FeaturedProduct
    autocomplete_fields = ["product"]
    module = _("Zite69")
    name = _("Featured Product")
    render_template = "cmsplugins/featured_product.html"
    allow_children = True
    parent_classes = ["FeaturedProductCollectionPlugin"]

    def render(self, context, instance, placeholder):
        context.update({"instance": instance})
        return context

@plugin_pool.register_plugin
class GroupBuyProductPlugin(CMSPluginBase):
    model = GroupBuyProduct
    autocomplete_fields = ["product"]
    module = _("Zite69")
    name = _("Group Buy")
    render_template = "cmsplugins/group_buy.html"
    allow_children = False
    
    def render(self, context, instance, placeholder):
        context.update({"instance": instance})
        return context

@plugin_pool.register_plugin
class AdaCollabProductPlugin(CMSPluginBase):
    model = AdaCollabProduct
    autocomplete_fields = ["product"]
    module = _("Zite69")
    name = _("ADA Collabs")
    render_template = "cmsplugins/ada_collabs.html"
    allow_children = False

    def render(self, context, instance, placeholder):
        context.update({"instance": instance})
        return context

@plugin_pool.register_plugin
class GiftsProductPlugin(CMSPluginBase):
    model = GiftsProduct
    autocomplete_fields = ["product"]
    module = _("Zite69")
    name = _("Gifts and Games Product")
    render_template = "cmsplugins/gift_product.html"
    allow_children = False

    def render(self, context, instance, placeholder):
        context.update({"instance": instance})
        return context

