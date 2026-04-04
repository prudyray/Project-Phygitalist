# from typing import Any, Mapping
from django import forms
# from django.forms.renderers import BaseRenderer
# from django.forms.utils import ErrorList
from phonenumber_field.formfields import PhoneNumberField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from shop.apps.main.utils.sms import send_phone_otp
from shop.apps.main.utils.email import send_email_otp
from .utils import generate_otp
from django.contrib.auth import get_user_model, authenticate
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
# from shop.apps.main.utils.common import dump
import logging
from django.core.validators import validate_email
#from phonenumber_field.validators import validate_phonenumber
from phonenumber_field.validators import validate_international_phonenumber

logger = logging.getLogger('shop.apps.otp')

class RequestOtpFormMixin(object):
    def request_otp(self):
        User = get_user_model()
        #dump(self.fields, logger)
        email = self.cleaned_data.get('email')
        phone = self.cleaned_data.get('phone')
        try:
            logger.debug("Inside request_otp")
            if email is not None:
                logger.debug(f"In RequestOtpFormMixin we have email: {email}")
                user = User.objects.get(email=email)
                otp = generate_otp(user, email=True)
                logger.debug(f"Generated OTP: {otp}")
                if otp:
                    resp = send_email_otp(user.email, otp)
                    logger.debug(f"Got response from sending email otp: {resp}")
            elif phone is not None:
                logger.debug(f"In RequestOtpFormMixin we have phone: {phone}")
                user = User.objects.get(phone=phone)
                otp = generate_otp(user, phone=True)
                logger.debug(f"Generated phone OTP: {otp}")
                if otp:
                    resp = send_phone_otp(user.phone, otp)
                    #logger.debug(f"Got response from sending phone otp: {resp}")
            else:
                raise ValueError(_("Badly configured either email or phone field must be defined"))
            return True
        except User.DoesNotExist:
            logger.warning(f"FAILED LOGIN ATTEMPT by email: {email}, phone: {phone}")
            return False

class EmailOtpRequestForm(forms.Form, RequestOtpFormMixin):
    email = forms.EmailField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_id = "id-request-email-otp"

        self.helper.add_input(Submit(name="email-form", value="Request OTP by Email"))

class PhoneOtpRequestForm(forms.Form, RequestOtpFormMixin):
    phone = PhoneNumberField(required=True, region="IN")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_id = "id-requesst-phone-otp"

        self.helper.add_input(Submit(name="phone-form", value="Request OTP to Phone"))

class OtpLoginMixin(object):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields['otp'] = forms.CharField(max_length=10)

    def do_login(self):
        User = get_user_model()
        if hasattr(self, 'email'):
            try:
                user = User.objects.get(email=self.email)

            except User.DoesNotExist:
                raise ValidationError(_("Invalid Credentials Provided"))

class EmailPhoneOtpRequestForm(forms.Form):
    email_phone = forms.CharField(label=_("Email or Phonenumber"), max_length=128, required=True, help_text=_("Please enter email address or your phone number"))

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_id = 'id-request-otp'

        self.helper.add_input(Submit(name="otp-request-form", value="Request OTP"))

    def clean_email_phone(self):
        valid_email = False
        valid_phone = False
        email_phone = self.cleaned_data['email_phone']
        try:
            validate_email(email_phone)
            valid_email = True
            self.valid_email = True
        except ValidationError:
            pass

        if not valid_email:
            try:
                validate_international_phonenumber(email_phone)
                valid_phone = True
                self.valid_phone = True
            except ValidationError:
                pass

        if not valid_email and not valid_phone:
            raise ValidationError(_("Please enter either a valid email address or phone number"), code="invalid")

        return email_phone

    def request_otp(self):
        from django.conf import settings as django_settings
        User = get_user_model()
        data = self.cleaned_data.get("email_phone")
        logger.debug(f"EmailPhoneOtpRequestForm.request_otp called for: {data}")
        logger.debug(f"EmailPhoneOtpRequestForm.request_otp: SMS_LIVE={getattr(django_settings, 'SMS_LIVE', False)}")

        user_kw_args = {}
        generate_kw_args = {}
        valid_email = getattr(self, 'valid_email', False)
        valid_phone = getattr(self, 'valid_phone', False)
        logger.debug(f"EmailPhoneOtpRequestForm.request_otp: valid_email={valid_email}, valid_phone={valid_phone}")
        logger.debug(logger.handlers)
        if valid_email:
            user_kw_args["email"] = data
            generate_kw_args["email"] = True
            logger.debug(f"Got valid email, requesting otp for {data}")
        elif valid_phone:
            user_kw_args["phone"] = data
            generate_kw_args["phone"] = True
            logger.debug(f"Got valid phonenumber, requesting otp for {data}")
        else:
            raise ValueError(_("Fatal error this should never happen. If neither email or phone is valid then the validation should fail"))

        try:
            user = User.objects.get(**user_kw_args)
            logger.debug(f"EmailPhoneOtpRequestForm.request_otp: found user={user}")
            otp = generate_otp(user, **generate_kw_args)
            logger.debug(f"EmailPhoneOtpRequestForm.request_otp: generate_otp returned otp={'[SET]' if otp else '[EMPTY]'}")
            if otp:
                if valid_email:
                    resp = send_email_otp(user.email, otp)
                    logger.debug(f"Sent email otp to user: {user}, got response: {resp}")
                else:
                    resp = send_phone_otp(user.phone, otp)
                    logger.debug(f"Sent phone otp to user: {user} got response: {resp}")
                return True
            else:
                logger.error("EmailPhoneOtpRequestForm.request_otp: generate_otp returned falsy value")
                raise ValueError(_("Generate OTP failed"))
        except User.DoesNotExist:
            logger.warning(f"EmailPhoneOtpRequestForm.request_otp: User not found for {user_kw_args}")
            return False


class OtpVerificationForm(forms.Form):
    email_phone = forms.CharField(label=_("Email or Phone number"), max_length=256, required=True)
    otp = forms.CharField(max_length=10, label=_("OTP"))
    type = forms.CharField(widget=forms.HiddenInput())
    field_next = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, request=None, *args, **kwargs) -> None:
        self.request = request
        self.user_cache = None

        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_id = "login-form"
        self.helper.add_input(Submit(name="login", value="Login"))

    def clean(self):
        email_phone = self.cleaned_data.get('email_phone')
        field_type = self.cleaned_data.get('type')
        otp = self.cleaned_data.get('otp')
        logger.debug(f"Attempting to authenticate: email_phone: {email_phone}, otp: {otp}")
        logger.debug(f"Got field_type {field_type}")
        auth_kw_args = {"otp": otp}
        if field_type == "email":
            auth_kw_args.update({"email": email_phone})
        elif field_type == 'phone':
            auth_kw_args.update({"phone": email_phone})
        else:
            raise ValidationError(_("Invalid Type"))

        if email_phone is not None and otp is not None:
            self.user_cache = authenticate(self.request, **auth_kw_args)
            logger.debug(f"authenticate returned: {self.user_cache}")
            if self.user_cache is None:
                raise ValidationError(_("Invalid Credentials"))
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError(_("Account is not active. Please contact the administrator"))

    def get_user(self):
        return self.user_cache
