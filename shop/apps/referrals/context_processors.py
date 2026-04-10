def user_referral(request):
    """
    Adds `user_referral` to the template context — the logged-in user's
    general referral link, or None for anonymous visitors.

    Caches the referral PK in the session to avoid a filter(user, label)
    query on every request. PK lookup on cache hit is fast (indexed).
    """
    if not request.user.is_authenticated:
        return {"user_referral": None}

    from shop.apps.referrals.models import Referral

    cached_pk = request.session.get('_user_referral_pk')
    if cached_pk:
        try:
            return {"user_referral": Referral.objects.get(pk=cached_pk)}
        except Referral.DoesNotExist:
            pass  # stale cache — fall through to re-fetch

    referral = Referral.objects.filter(user=request.user, label="general").first()
    if not referral:
        referral = Referral.create(user=request.user, redirect_to="/", label="general")

    request.session['_user_referral_pk'] = referral.pk  # int — JSON serializable
    return {"user_referral": referral}
