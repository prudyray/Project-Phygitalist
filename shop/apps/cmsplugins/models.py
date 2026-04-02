from django.db import models
from django.utils.autoreload import cached_property
from shop.apps.catalogue.models import Product
from cms.models import CMSPlugin
from cms.models.fields import PlaceholderRelationField
from cms.plugin_pool import plugin_pool
from cms.utils.placeholder import get_placeholder_from_slot
from django.utils.translation import gettext as _

class FeaturedProductCollection(CMSPlugin):
    name = models.CharField(_("Collection Name"), max_length=32, blank=False, null=False)

class FeaturedProduct(CMSPlugin):
    class LabelType(models.TextChoices):
        HOT = 'hot', _("Hot")
        BEST = 'best', _("Bestseller")
        NEW = 'new', _("New")
        SALE = 'sale', _("Sale")

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    label = models.CharField(_("Label"), max_length=32, blank=True, null=True)
    label_type = models.CharField(_("Label Type"), choices=LabelType.choices, max_length=8, blank=True, null=True)

    def get_label_type(self):
        return self.LabelType(self.label_type)

    def get_template(self):
        return "cmsplugins/featured_products.html"

class GroupBuyProduct(CMSPlugin):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

class AdaCollabProduct(CMSPlugin):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

class GiftsProduct(CMSPlugin):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

class ImageCarousel(CMSPlugin):
    pass

class HeroCarousel(CMSPlugin):
    pass

class HeroSlide(CMSPlugin):
    slide_image = models.ImageField(upload_to="plugins/hero_carousel")
