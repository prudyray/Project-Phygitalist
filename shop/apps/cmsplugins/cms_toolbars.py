from cms.toolbar_pool import toolbar_pool
from cms.toolbar_base import CMSToolbar


@toolbar_pool.register
class ViewPageToolbar(CMSToolbar):
    def populate(self):
        self.toolbar.add_link_item(
            name='Home',
            url='/',
        )
