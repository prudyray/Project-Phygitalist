"""
Signals for search events.
"""

from django.dispatch import Signal

# Fired when a user performs a search query
user_search = Signal()

# Fired when a search query returns results
query_hit = Signal()
