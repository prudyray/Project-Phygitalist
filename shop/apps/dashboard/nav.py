from oscar.apps.dashboard.nav import Node as OscarNode


class Node(OscarNode):
    def __init__(self, label, url_name=None, url_args=None, url_kwargs=None,
                 access_fn=None, icon=None, active=False):
        super().__init__(
            label=label,
            url_name=url_name,
            url_args=url_args,
            url_kwargs=url_kwargs,
            access_fn=access_fn,
            icon=icon,
        )
        self.active = active

    def filter(self, user):
        if not self.is_visible(user):
            return None
        node = Node(
            label=self.label,
            url_name=self.url_name,
            url_args=self.url_args,
            url_kwargs=self.url_kwargs,
            access_fn=self.access_fn,
            icon=self.icon,
            active=self.active
        )
        for child in self.children:
            if child.is_visible(user):
                node.add_child(child)
        return node
