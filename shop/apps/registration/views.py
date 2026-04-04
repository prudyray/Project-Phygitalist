from collections import OrderedDict, defaultdict
from re import T
from django.shortcuts import render, redirect
from django.conf import settings
from django import forms
from django.urls import reverse_lazy, reverse
from django.utils.html import urlencode
from django.views.generic import TemplateView, View
from django.http import HttpResponseRedirect, JsonResponse
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core import serializers
from django.core.exceptions import SuspiciousOperation
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from django.views.generic.edit import FormMixin
from django.utils.decorators import classonlymethod
from django.contrib import messages
from django.core import serializers
import json

from datetime import datetime

from django.views.generic.edit import FormView
from shop.apps.address.utils import get_default_country
from shop.apps.main.errors import ConfigurationError
from shop.apps.main.utils.sms import send_phone_otp
from shop.apps.main.utils.email import send_email_verification, send_mail_mentor
from shop.apps.main.utils.urls import get_site_base_uri
from shop.apps.otp.utils import generate_otp
from phonenumber_field.phonenumber import PhoneNumber
from phonenumber_field.validators import validate_international_phonenumber
from formtools.wizard.views import SessionWizardView
from formtools.wizard.forms import ManagementForm
from shop.apps.main.models import State, Postoffice
from shop.apps.seller.models import SellerPickupAddress, Seller
from shop.apps.registration.models import SellerRegistration
from shop.apps.zitepayment.models import BankAccount

from .forms import REGISTRATION_FORM_TEMPLATES, OnboardingForm, PickupAddressForm
from .models import seller_registration_filestorage

import json
import logging
import os
import traceback

logger = logging.getLogger(__name__)

User = get_user_model()
india = None

class HomeView(TemplateView):
    template_name = 'registration/home.html'

class SellerRegistrationWizard(SessionWizardView):
    template_name = 'registration/seller.html'
    file_storage = seller_registration_filestorage

    def get_template_names(self):
        # logger.debug(f"Returning template: {REGISTRATION_FORM_TEMPLATES[self.steps.current]} for step {self.steps.current}")
        return [REGISTRATION_FORM_TEMPLATES[self.steps.current]]

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        kwargs['request'] = self.request
        return kwargs

    def process_step(self, form):
        # logger.debug(f"in process_step. form: {form}")
        # logger.debug(form)
        logger.debug(f"in process_step, current step: {self.steps.current}")
        return super().process_step(form)

    def render_goto_step(self, goto_step, **kwargs):
        logger.debug("inside render_goto_step")
        logger.debug(f"goto_step: {goto_step}")
        logger.debug(f"kwargs: {kwargs}")
        return super().render_goto_step(goto_step, **kwargs)

    def render_revalidation_failure(self, step, form, **kwargs):
        logger.debug("inside render_revalidation_failure")
        logger.debug(f"step: {step}")
        logger.debug(f"form: {form.__class__}")
        return super().render_revalidation_failure(step, form, **kwargs)

    def _get_debug_form_list(self):
        form_list = OrderedDict()
        condition_list = OrderedDict()
        condition_result_list = OrderedDict()
        for form_key, form_class in self.form_list.items():
            # try to fetch the value from condition list, by default, the form
            # gets passed to the new list.
            condition = self.condition_dict.get(form_key, True)
            # logger.debug(f"got condition: {condition} for form_key: {form_key}")
            if callable(condition):
                # call the value if needed, passes the current instance.
                condition_list[form_key] = condition
                result = condition(self)
                condition_result_list[form_key] = result
                condition = result
            if condition:
                form_list[form_key] = form_class
        return form_list, condition_list, condition_result_list


    def post(self, *args, **kwargs):
        """
        This method handles POST requests.

        The wizard will render either the current step (if form validation
        wasn't successful), the next step (if the current step was stored
        successful) or the done view (if no more steps are available)
        """
        # Look for a wizard_goto_step element in the posted data which
        # contains a valid step name. If one was found, render the requested
        # form. (This makes stepping back a lot easier).
        wizard_goto_step = self.request.POST.get('wizard_goto_step', None)
        if wizard_goto_step and wizard_goto_step in self.get_form_list():
            return self.render_goto_step(wizard_goto_step)

        # Check if form was refreshed
        management_form = ManagementForm(self.request.POST, prefix=self.prefix)
        if not management_form.is_valid():
            raise SuspiciousOperation(_('ManagementForm data is missing or has been tampered.'))

        form_current_step = management_form.cleaned_data['current_step']
        if (form_current_step != self.steps.current and
                self.storage.current_step is not None):
            logger.debug(f"Changing current step from: {self.steps.current} to: {form_current_step}")
            # form refreshed, change current step
            self.storage.current_step = form_current_step
        logger.debug(f"form_current_step: {form_current_step}")
        try:
            form = self.get_form(data=self.request.POST, files=self.request.FILES)
        except KeyError as e:
            self.errors = {"error": f"Failed to get step: {self.steps.current}"}
            ts = datetime.now().strftime("%Y-%m-%d:%H:%M:%S")
            trace_filename = f"{ts}.log"
            pickle_forms_filename = f"{ts}-forms.pkl"
            pickle_condition_filename = f"{ts}-condition.pkl"
            pickle_result_filename = f"{ts}-result.pkl"
            logger.debug(f"Got a 500 error in the wizard and self.request.user: {self.request.user}")
            if self.request.user and self.request.user.username:
               trace_filename = f"{self.request.user.username}-{trace_filename}"
               pickle_forms_filename = f"{self.request.user.username}-{pickle_forms_filename}"
               pickle_condition_filename = f"{self.request.user.username}-{pickle_condition_filename}"
               pickle_result_filename = f"{self.request.user.username}-{pickle_result_filename}"
            elif self.request.session.get('user_id', -1) != -1:
                user_id = self.request.session.get('user_id', -1)
                user = User.objects.get(id=user_id)
                trace_filename = f"{user.username}-{trace_filename}"
                pickle_forms_filename = f"{user.username}-{pickle_forms_filename}"
                pickle_condition_filename = f"{user.username}-{pickle_condition_filename}"
                pickle_result_filename = f"{user.username}-{pickle_result_filename}"

            forms_list, condition_list, result_list = self._get_debug_form_list()
            import dill as pickle
            with open(os.path.join(settings.LOG_DIR, pickle_forms_filename), "wb") as fp:
                pickle.dump(forms_list, fp)
            with open(os.path.join(settings.LOG_DIR, pickle_condition_filename), "wb") as fp:
                pickle.dump(condition_list, fp)
            with open(os.path.join(settings.LOG_DIR, pickle_result_filename), "wb") as fp:
                pickle.dump(result_list, fp)
            with open(os.path.join(settings.LOG_DIR, trace_filename), "w") as f:
                f.write("".join(traceback.format_stack()))

            return self.render_goto_step('error')


        # and try to validate
        if form.is_valid():
            # if the form is valid, store the cleaned data and files.
            self.storage.set_step_data(self.steps.current, self.process_step(form))
            self.storage.set_step_files(self.steps.current, self.process_step_files(form))

            # check if the current step is the last step
            if self.steps.current == self.steps.last:
                # no more steps, render done view
                return self.render_done(form, **kwargs)
            else:
                # proceed to the next step
                return self.render_next_step(form)
        return self.render(form)


    def get_form(self, step=None, data=None, files=None):
        logger.debug("inside wizard get_form")
        if step is None:
            step = self.steps.current
            logger.debug(f"step argument passed in is None so it is now set to current: {step}")
        # form_list = self.get_form_list()
        form_class = self.get_form_list()[step]
        # prepare the kwargs for the form instance.
        kwargs = self.get_form_kwargs(step)
        kwargs.update({
            'data': data,
            'files': files,
            'prefix': self.get_form_prefix(step, form_class),
            'initial': self.get_form_initial(step),
        })
        if issubclass(form_class, (forms.ModelForm, forms.models.BaseInlineFormSet)):
            # If the form is based on ModelForm or InlineFormSet,
            # add instance if available and not previously set.
            kwargs.setdefault('instance', self.get_form_instance(step))
        elif issubclass(form_class, forms.models.BaseModelFormSet):
            # If the form is based on ModelFormSet, add queryset if available
            # and not previous set.
            kwargs.setdefault('queryset', self.get_form_instance(step))
        return form_class(**kwargs)

    def done(self, form_list, **kwargs):
        url = get_site_base_uri(site_id=settings.DEFAULT_SITE_ID)
        return HttpResponseRedirect(url)

    def get_auth_next_step(self, step):
        if not self.request.user.phone_verified:
            return 'mobile'
        if not self.request.user.email_verified:
            return 'email'
        return 'business'

class UsernameAvailableJson(View):
   def post(self, request, *args, **kwargs):
       try:
           data = json.loads(request.body)
       except json.JSONDecodeError:
           return JsonResponse({"error": "Invalid json input"})

       username = data.get('username', '')
       logger.debug(f"got username: {username}")

       if username == "":
            return JsonResponse({"error": "Username is required"})

       try:
           User.objects.get(username=username)
           return JsonResponse({"status": "unavailable"})
       except User.DoesNotExist:
           return JsonResponse({"status": "available"})

class JsonRequestResponseMixin(object):
    def get_data(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid json input"})

        return data

    def get_user(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return request.user

        user_id = request.session.get('user_id', -1)
        if user_id == -1:
            return JsonResponse({"error": "System error: User not found in session"})


        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({"error": "Username is not available"})
        logger.debug(f"Found user in session: {user}")

        return user


class SendPhoneOtpJson(View, JsonRequestResponseMixin):

    def post(self, request, *args, **kwargs):
        data = self.get_data(request, *args, **kwargs)
        if type(data) == JsonResponse:
            return data

        user = self.get_user(request, *args, **kwargs)
        if type(user) == JsonResponse:
            return user

        phone = data.get('phone', '')
        if phone == '':
            return JsonResponse({"error": "Phone number is required"})

        try:
           validate_international_phonenumber(phone)
        except ValidationError:
            return JsonResponse({"error": "Invalid phone number"})

        phone_object = PhoneNumber.from_string(phone_number=phone)
        logger.debug(phone_object)

        try:
            pu = User.objects.get(phone=phone_object)
            if pu.id != user.id:
                return JsonResponse({"error": "Phone number already in use, please login with your number to proceed"})
        except User.DoesNotExist:
            user.phone=phone_object
            user.save()

        otp = generate_otp(user, phone=True)
        logger.debug(f"created user: {user} sending phone: {user.phone} an otp: {otp}")

        resp = send_phone_otp(user.phone, otp, sms_template=settings.SMS_VALIDATE_PHONE_OTP)
        logger.debug(f"Got response after sending phone otp: {resp}")

        return JsonResponse({"status": "success", "id": user.id})

class SendEmailOtpJson(View, JsonRequestResponseMixin):
    def post(self, request, *args, **kwargs):
        data = self.get_data(request, *args, **kwargs)
        if type(data) == JsonResponse:
            return data

        user = self.get_user(request, *args, **kwargs)
        if type(user) == JsonResponse:
            return user

        email = data.get('email', '')
        if email == '':
            return JsonResponse({"error": "Email address cannot be blank"})

        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({"error": "Invalid email address, please check and re-enter"})


        if User.objects.filter(email=email).exclude(pk=user.pk).exists():
            return JsonResponse({"error": "Email address already in use, please login with your email or user to proceed"})

        user.email = email
        user.save()

        otp = generate_otp(user, email=True)
        logger.debug(f"created user: {user}, sending email: {user.email} an otp: {otp}")

        resp = send_email_verification(email, otp)
        #logger.debug(f"Response after sending email otp: {resp}")

        logger.debug(f"Sent {user.email} an otp: {otp}")

        return JsonResponse({"status": "success", "id": user.id})

@method_decorator(cache_page(60*30), name='dispatch')
class PincodeListJson(View, JsonRequestResponseMixin):
    def get(self, request, *args, **kwargs):
        pincode_prefix = request.GET.get('term', '')
        action = request.GET.get('action', 'pincode')
        if len(pincode_prefix) < 3:
            return JsonResponse([])

        results = []
        if action == 'pincode':
            results = list(Postoffice.objects.filter(pincode__startswith=pincode_prefix).order_by('pincode').values_list('pincode', flat=True).distinct()[:20])
        elif action == 'place':
            pincodes = Postoffice.objects.filter(pincode=pincode_prefix).order_by('office')
            results = [ {'id': p.id, 'place': p.office} for p in pincodes ]

        return JsonResponse(results, safe=False)

class ValidatePhoneOtp(View, JsonRequestResponseMixin):

    def post(self, request, *args, **kwargs):
        data = self.get_data(request, *args, **kwargs)
        if type(data) == JsonResponse:
            return data

from crispy_forms.layout import Field
class UnprefixedHiddenInput(forms.HiddenInput):

    def render(self, name, value, attrs=None, renderer=None):
        logger.debug("Inside render")
        return super().render(name, value, attrs, renderer)

    def get_context(self, name, value, attrs=None):
        logger.debug("Inside get_context")
        ctx = super().get_context(name, value, attrs)
        ctx['widget']['name'] = 'submit_id'
        logger.debug(ctx['widget']['template_name'])
        logger.debug("Inside get_context for hidden widget")
        return ctx

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        attrs['data-dash'] = 'yes'
        logger.debug("Inside build_attrs")
        return attrs

class MultiFormView(TemplateView):
    # form_classes is a dictionary of {"key": FormClass}
    form_classes = {}
    # key_property_lookup is a dictionary of lookups for forms that are instances of ModelForm.
    # this property does a lookup for that particular property and deeply nested string 
    # the deeply nested property string starts from self - ie this class.
    # so a property string could look like 'request.user.seller_registration'
    # an example key_property_lookup is {"pickup": {"user": "request.user.seller.sellerpickupaddress"}}
    key_property_lookup = {}
    template_name = "oscar/dashboard/wizard.html"
    success_url = reverse_lazy("dashboard-welcome")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_instances = {}  # Store existing model instances
        self.form_classes = kwargs.get('form_classes', {})
        self.forms = OrderedDict()

        request = kwargs.get('request', None)
        if request:
            logger.debug("We got request")
            self.request = request
        else:
            logger.debug("No request in kwargs __init__ in view")

    def update_forms(self):
        # Prepare forms with submit_id
        submit_form = self.get_submit_form()
        for k, form_class in self.form_classes.items():
            # Try to get existing instance for ModelForms
            instance = self.get_existing_instance(form_class, k)
            # Initialize form with potential instance
            form_kwargs = {
                'prefix': k,
                **self.get_form_kwargs(prefix=k)
            }

            if self.request.method == "POST":
                form_kwargs['data'] = self.request.POST
                form_kwargs['files'] = self.request.FILES

            # Add instance only for ModelForms
            if instance:
                form_kwargs['instance'] = instance

            self.form_instances[k] = instance
            if self.request.method == "POST":
                if submit_form == k:
                    self.forms[k] = form_class(**form_kwargs)
                else:
                    self.forms[k] = form_class(**{k:v for k, v in form_kwargs.items() if k not in ['data', 'files']})
            else:
                self.forms[k] = form_class(**form_kwargs)

            self.forms[k].fields['submit_id'] = forms.CharField(initial=k)
            self.forms[k].helper.layout.append(Field('submit_id', type="hidden", template="registration/widgets/unprefixed_field.html"))
            self.forms[k].fields['submit_id'].widget.attrs['name'] = 'submit_id'

    def _get_completion_percentage(self):
        completion = 60
        if hasattr(self.request.user, 'seller') and self.request.user.seller.pickup_addresses.count() > 0:
            completion += 10
        if self.request.user.bankaccount_set.count() >= 1:
            completion += 10
        if hasattr(self.request.user, 'seller') and self.request.user.seller.shipping_preference != '':
            completion += 10

        return completion

    def get_existing_instance(self, form_class, key):
        """
        Retrieve existing model instance for ModelForms
        """
        # Check if this is a ModelForm
        if not issubclass(form_class, forms.ModelForm):
            logger.debug("Returning None because form_class is not a ModelForm")
            return None

        if not hasattr(self.request.user, 'seller'):
            logger.debug("Creating a seller for the current logged in user")
            try:
                registration = SellerRegistration.objects.get(user=self.request.user)
            except SellerRegistration.DoesNotExist:
                raise ConfigurationError(_("User must never come here without first registering"))

            self.seller = Seller.objects.create(
                    user = self.request.user,
                    name = registration.shop_name,
                    handle = registration.shop_handle,
                    gstin = registration.gstin,
                    pan = registration.pan,
                    )
        else:
            self.seller = self.request.user.seller
        if key == "pickup":
            logger.debug("Returning instance for key = pickup")
            try:
                return SellerPickupAddress.objects.get(seller=self.seller)
            except SellerPickupAddress.DoesNotExist:
                return None
        elif key == "bank":
            logger.debug("Returning instance for key = bank")
            logger.debug(f"User: {self.request.user}")
            try:
                return BankAccount.objects.get(user=self.request.user)
            except BankAccount.DoesNotExist:
                return None
        elif key == "seller" or key == "tnc":
            return self.seller

        return None

    def get_form_kwargs(self, prefix=""):
        """
        Additional kwargs for form initialization
        Can be overridden in subclasses
        """
        if hasattr(self, 'request'):
            return {
                'request': self.request  # Pass request to forms that might need it
            }

        return {}

    def get(self, request, *args, **kwargs):
        logger.debug("Inside get")
        if not self.request.user.is_authenticated:
            reverse_url = reverse('account_login')
            return redirect(f"{reverse_url}?next=/dashboard/onboarding/")
        if not hasattr(self.request.user, 'seller_registration'):
            messages.warning(self.request, 'You must first register as a seller')
            return redirect("registration:home")
        if not self.request.user.seller_registration.approved:
            messages.warning(self.request, 'Your registration is not approved')
            return redirect("notapproved")

        context = self.get_context_data(**kwargs)
        #context['forms'] = self.forms
        logger.debug("forms:")
        logger.debug(self.forms)
        return self.render_to_response(context)

    def all_forms_valid(self):
        return all([form.is_valid() for _, form in self.forms.items()])

    def get_submit_form(self):
        return self.request.POST.get('submit_id', '') if self.request.method == "POST" else ""

    def post(self, request, *args, **kwargs):
        # Determine which form was submitted
        key = self.get_submit_form()

        logger.debug(f"key: {key}")
        # Reinitialize forms with POST data
        #self.forms = OrderedDict()
        form_class = self.form_classes.get(key)
        instance = self.get_existing_instance(form_class, key)
        form_kwargs = {
            'prefix': key,
            'data': request.POST,
            'files': request.FILES,
            **self.get_form_kwargs(prefix=key)
        }
        if instance:
            form_kwargs['instance'] = instance

        self.forms[key] = form_class(**form_kwargs)

        if self.forms[key] and self.forms[key].is_valid():
            return self.form_valid(self.forms[key], key)
        else:
            return self.form_invalid()

    def form_valid(self, form, form_key):
        """
        Handle form saving for both ModelForms and regular Forms
        """
        global india
        # For ModelForms, save the instance
        if isinstance(form, forms.ModelForm):
            logger.debug(f"Being called inside form_valid with form {form} and key: {form_key}")
            instance = form.save(commit=False)

            # Try to set user if possible
            try:
                instance.user = self.request.user
            except AttributeError:
                pass

            if india is None:
                india = get_default_country()

            if form_key == "pickup":
                instance.seller = self.seller
                instance.country = india
                messages.success(self.request, "Your pickup address has been saved successfully, please continue with adding your bank details")
            elif form_key == "bank":
                messages.success(self.request, "Your bank details have been saved successfully, please continue with adding your signature, GST doc & shipping")
            elif form_key == 'seller':
                messages.success(self.request, "Your shipping preferences, GST/PAN and signature have been saved successfully. Please accept the Terms & Conditions")
            elif form_key == 'tnc':
                messages.success(self.request, "Thank you for completing your onboarding with us. You may start adding products to your store catalogue. You will be notified via email when your Seller account is fully functional.")

            instance.save()
            if form_key == 'tnc':
                logger.debug("At last step seller - checking if all forms are valid")
                if self.all_forms_valid():
                    logger.debug("All forms valid redirecting to success_url")
                    return HttpResponseRedirect(f"{self.success_url}?toolbar_off")
        else:
            # For regular forms, you might want to do something else
            # This could be overridden in a subclass
            # We are only using ModelForms currently, so this is never called
            messages.success(self.request, "Form submitted successfully!")

        return HttpResponseRedirect(self.request.path)

    def form_invalid(self):
        """
        Render the page with validation errors
        """
        context = self.get_context_data(forms=self.forms)
        return self.render_to_response(context)

    def _is_gst_uploaded(self):
        return all([self.request.user.seller_registration.gstin != '', 
                    hasattr(self.request.user, 'seller') and (
                        (self.request.user.seller_registration.gst_status == 'Y' and self.request.user.seller.gstin_file) 
                        or 
                        (self.request.user.seller_registration.gst_status != 'Y' and self.request.user.seller.pan_file)
                    )])

    def get_steps(self):
        steps = defaultdict(lambda : False)
        if self.request.user.phone_verified and self.request.user.email_verified:
            steps['phone'] = True
        steps['password'] = True
        if self._is_gst_uploaded():
            steps['gst'] = True
        if self.request.user.seller_registration.shop_name != '':
            steps['shop'] = True
        if hasattr(self.request.user, 'seller') and self.request.user.seller.pickup_addresses.count() > 0:
            steps['pickup'] = True
        if hasattr(self.request.user, 'seller') and self.request.user.seller.signature_file:
            steps['signature'] = True
        if hasattr(self.request.user, 'seller') and self.request.user.seller.shipping_preference != '':
            steps['shipping'] = True
        if self.request.user.bankaccount_set.count() > 0:
            steps['bank'] = True

        logging.debug("in get_steps: ")
        logging.debug(steps)
        # logging.debug(hasattr(self.request.user, 'seller') and self.request.seller.signature_file != None)

        return steps

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['registration'] = self.request.user.seller_registration
        ctx['registration_json'] = serializers.serialize('json', [self.request.user.seller_registration])
        ctx['completion_percentage'] = self._get_completion_percentage()
        ctx['steps'] = self.get_steps()
        self.update_forms()
        ctx['forms'] = self.forms
        return ctx


    @classmethod
    def as_view(cls, form_classes=None, **initkwargs):
        """
        Class method to create the view with form classes
        """
        if not form_classes:
            raise ValueError("form_classes must be provided")

        initkwargs['form_classes'] = form_classes
        return super().as_view(**initkwargs)

class WelcomePage(View):
    template_name = "oscar/dashboard/welcome.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        logger.debug("inside WelcomePage.post")
        resp = send_mail_mentor(request.user.seller)
        request.user.is_staff = True
        request.user.save()
        logger.debug(f"Response after sending send_mail_mentor: {resp}")
        return HttpResponseRedirect(reverse_lazy("dashboard:index"))
