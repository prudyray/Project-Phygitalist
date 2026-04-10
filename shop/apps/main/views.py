from django.db.models.functions import Sign
from django.shortcuts import render
from django.views.generic.edit import FormView
from django.views.generic import TemplateView
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.conf import settings
from .utils.email import send_email_otp
import logging
from allauth.account.views import LoginView as OGLoginView
from allauth.account.forms import RequestLoginCodeForm
from allauth.utils import get_form_class
from allauth.account import app_settings
from shop.apps.user.forms import Zite69SignupForm
from shop.apps.otp.forms import EmailPhoneOtpRequestForm, OtpVerificationForm
from shop.apps.catalogue.models import Product
from shop.apps.main.forms import BuyQuickForm
from shop.apps.main.utils.jaas_jwt import JaaSJwtBuilder

logger = logging.getLogger("shop.apps.main")

# Create your views here.

class LoginView(OGLoginView):
    
    def dispatch(self, request, *args, **kwargs):
        next_url = self.get_next_url()
        logger.debug("login dispatch: next_url: ")
        logger.debug(next_url)
        if next_url != '' and next_url is not None:
            request.session['next'] = next_url
            request.session.save()

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['request_code_form'] = EmailPhoneOtpRequestForm()
        ctx['signup_form'] = Zite69SignupForm()
        ctx['verify_code_form'] = OtpVerificationForm()

        return ctx

class BuyQuickView(FormView):
    form_class = BuyQuickForm
    template_name = "oscar/catalogue/buyquick.html"
    success_url = reverse_lazy("checkout:index")

    def form_valid(self, form):
        product_id = form.cleaned_data.get('product_id')
        logger.debug("product_id")
        logger.debug(product_id)
        product = Product.objects.get(id=product_id)
        logger.debug(product)
        logger.debug(self.request.basket)
        self.request.basket.add_product(product, 1)
        logger.debug(self.success_url)
        return HttpResponseRedirect(self.success_url)

class VideoDemoView(TemplateView):
    template_name = "video_demo.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        with open(settings.JAAS_PRIVATE_KEY_PATH, 'r') as f:
            private_key = f.read()

        # Sellers and staff join as moderators; buyers join as participants
        is_moderator = user.is_authenticated and (user.is_staff or hasattr(user, 'seller'))

        token = JaaSJwtBuilder() \
            .withDefaults() \
            .withApiKey(settings.JAAS_API_KEY) \
            .withAppID(settings.JAAS_APP_ID) \
            .withUserName(user.get_full_name() or user.email if user.is_authenticated else 'Guest') \
            .withUserEmail(user.email if user.is_authenticated else '') \
            .withUserAvatar('') \
            .withModerator(is_moderator) \
            .signWith(private_key)

        # authlib jwt.encode() returns bytes
        ctx['jwt_token'] = token.decode('utf-8') if isinstance(token, bytes) else token
        ctx['jaas_app_id'] = settings.JAAS_APP_ID
        return ctx


def home(request):
    context = {}

    return render(request, 'main/index.html', context)

def test(request):
    resp = send_email_otp('arunkakorp@gmail.com', otp='123412', cc=['arun@kumars.io'])
    logger.debug("Got response from send_email_otp:")
    logger.debug(resp)

    return render(request, 'main/index.html')

def fivehundred(request):
    num = 1/0
    return render(request, 'error/500.html')

def not_found(request, exception):
    return render(request, "error/404.html", {}, status=404)

def server_error(request, exception=None):
    return render(request, "error/500.html", {}, status=500)

def unauthorized(request, exception=None):
    return render(request, "error/403.html", {}, status=403)

def csrf_failure(request, reason=""):
    logger.error("CSRF FAILURE")
    logger.error("reason=%r", reason)
    logger.error("path=%r", request.path)
    logger.error("method=%r", request.method)
    logger.error("origin=%r", request.META.get("HTTP_ORIGIN"))
    logger.error("referer=%r", request.META.get("HTTP_REFERER"))
    logger.error("raw_cookie=%r", request.META.get("HTTP_COOKIE"))
    logger.error("parsed_cookies=%r", request.COOKIES)
    logger.error("csrf_cookie=%r", request.COOKIES.get("csrftoken"))
    logger.error("post_csrf=%r", request.POST.get("csrfmiddlewaretoken"))
    return HttpResponseForbidden("CSRF verification failed.")
