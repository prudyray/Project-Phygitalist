"""
URL configuration for shop project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.apps import apps
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import JavaScriptCatalog
from django.views.generic import TemplateView, RedirectView
from debug_toolbar.toolbar import debug_toolbar_urls
from django.http import Http404, HttpResponseRedirect
from django.conf.urls import (handler404, handler500, handler403)
from django.contrib.sitemaps.views import sitemap
# from django.contrib.auth.decorators import permission_required
from shop.apps.registration.sitemaps import SITEMAPS
from shop.apps.registration.views import MultiFormView, WelcomePage
from shop.apps.registration.forms import BankDetailsForm, SellerPickupAddressForm, SellerRemainingForm, TnCForm
from shop.apps.seller.models import Seller
from shop.apps.main.decorators import check_perm_404
from shop.apps.main.views import LoginView
from shop.apps.seller.views import SellerDetailView

import logging
from django_downloadview import ObjectDownloadView
from django.shortcuts import HttpResponse
from rules.contrib.views import permission_required, objectgetter

logger = logging.getLogger("shop.urls_seller")

handler404 = 'shop.apps.main.views.not_found'
handler500 = 'shop.apps.main.views.server_error'
handler403 = 'shop.apps.main.views.unauthorized'

ONBOARDING_FORM_CLASSES = {
    "pickup": SellerPickupAddressForm,
    "bank": BankDetailsForm,
    "seller": SellerRemainingForm,
    "tnc": TnCForm
}

urlpatterns = i18n_patterns(
    path('sitemap.xml', sitemap, { "sitemaps": SITEMAPS }, name="seller.sitemap"),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    path('notapproved/', TemplateView.as_view(template_name='registration/notapproved.html'), name="notapproved"),
    path('review/', TemplateView.as_view(template_name="review.html"), name="registration-review"),
    path('dashboard/demo/', TemplateView.as_view(template_name='demo/index.html'), name="demo"),
    path('dashboard/onboarding/', MultiFormView.as_view(form_classes=ONBOARDING_FORM_CLASSES), name="onboarding-wizard"),
    path('select2/', include('django_select2.urls')),
    path('admin/', admin.site.urls),
    path('accounts/login/', LoginView.as_view()),
    path('accounts/order/<str:order_number>/', RedirectView.as_view(pattern_name='customer:order', permanent=True)),
    path('accounts/', include('allauth.urls')),
    path('messages/', include('django_messages.urls')),
    path('mentor/', TemplateView.as_view(template_name='main/mentor.html'), name="mentor"),
    path('sellerschool/', TemplateView.as_view(template_name='main/sellerschool.html'), name="sellerschool"),
    path('invitation/', include((apps.get_app_config('invitation').urls[0], 'invitation'), namespace='invitation')),
    path('otp/', include((apps.get_app_config('otp').urls[0], 'otp'), namespace='otp')),
    path('registration/', include((apps.get_app_config('registration').urls[0], 'registration'), namespace='registration')),
    path('dashboard/welcome/', WelcomePage.as_view(), name="dashboard-welcome"),
    path('dashboard/seller/', SellerDetailView.as_view(), name="dashboard-seller"),
    path('offers/', apps.get_app_config('offer').urls),
    path('dashboard/', apps.get_app_config('dashboard').urls),
    path('catalog/', apps.get_app_config('catalogue').urls),
    path('referrals/', include('shop.apps.referrals.urls', namespace='referrals')),
    path('accounts/', apps.get_app_config('customer').urls),
    path('', include('djangocms_forms.urls')),
    path('', include('cms.urls')),
    prefix_default_language=False,
)

urlpatterns = [
    path("protected/seller/<int:pk>/gstin/<str:filename>", check_perm_404('seller.view_media', fn=objectgetter(Seller, 'pk'))(ObjectDownloadView.as_view(model=Seller, file_field="gstin_file")), name="gtstin-file-protected-view"),
    path("protected/seller/<int:pk>/pan/<str:filename>", check_perm_404('seller.view_media', fn=objectgetter(Seller, 'pk'))(ObjectDownloadView.as_view(model=Seller, file_field="pan_file")), name="pan-file-protected-view"),
    path("protected/seller/<int:pk>/signature/<str:filename>", check_perm_404('seller.view_media', fn=objectgetter(Seller, 'pk'))(ObjectDownloadView.as_view(model=Seller, file_field="signature_file")), name="signature-file-protected-view"),
    ] + urlpatterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns = debug_toolbar_urls() + urlpatterns
