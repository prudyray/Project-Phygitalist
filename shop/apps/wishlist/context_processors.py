def wishlists(request):
    if not (hasattr(request, 'user') and request.user.is_authenticated):
          return {}

      count = request.session.get('_wishlist_count')
      if count is None:
          count = request.user.wishlists.count()
          request.session['_wishlist_count'] = count

      return {"wishlists_count": count}
