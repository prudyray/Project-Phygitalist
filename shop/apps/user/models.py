from typing import Any
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth import models as auth_models
from django.db import models
from oscar.apps.customer.abstract_models import AbstractUser
from oscar.core.loading import get_class, get_model
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from django.db.models import Q
from django.utils import timezone
from localflavor.in_.forms import INPANCardNumberFormField
from localflavor.in_.models import INPANCardNumberField
import logging
import re

logger = logging.getLogger("shop.apps.user.models")

#Address = get_model("address", "Address")

REX_UPI = re.compile(r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$")

class UserManager(auth_models.BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        """
        Creates and saves a User with the given email and
        password.
        """
        now = timezone.now()
        email = None
        if '@' in username:
            email = username
            email = UserManager.normalize_email(email)

        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_superuser', False)
        user = self.model(
            username=username,
            email=email,
            last_login=now,
            date_joined=now,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        u = self.create_user(username, password, **extra_fields)
        u.is_staff = True
        u.is_active = True
        u.is_superuser = True
        u.save(using=self._db)
        return u

@deconstructible
class validate_length:
    def __init__(self, length=15) -> None:
        self.length = length

    def __call__(self, value, **kwds: Any) -> Any:
        if len(str(value)) != self.length:
            raise ValidationError(_("Value %(value)s is not of %(length)s"), params={"value": value, "length": self.length})

    def __eq__(self, other):
        return self.length == other.length

def validate_upi(value):
    if not REX_UPI.match(value):
        raise ValidationError(_("UPI ID %(value)s does not appear to be valid"))

class User(AbstractUser):
    email = models.EmailField(_("Email Address"), blank=True, null=True)
    username = models.CharField(_("Username"), max_length=64, unique=True, blank=False)
    phone = PhoneNumberField(_("Phone Number"), region='IN', blank=False, null=True)
    email_verified = models.BooleanField(_("Verified Email"), default=False)
    phone_verified = models.BooleanField(_("Verified Phonenumber"), default=False)

    USERNAME_FIELD = "username"

    objects = UserManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(email__isnull=False) | Q(username__isnull=False) | Q(phone__isnull=False),
                name='not_all_null'
            ),
            models.UniqueConstraint(
                fields=['email'],
                condition=(~models.Q(email='') & models.Q(email__isnull=False)),
                name='unique_email_ifnotnull'
            ),
            models.UniqueConstraint(
                fields=['phone'],
                condition=(models.Q(phone__isnull=False)),
                name='unique_phone_ifnotnull'
            ),
        ]

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        logger.debug(f"user: {self.username}")
        if self.username == "":
            if self.email == "":
                logger.debug(f"number: {self.phone.national_number}")
                self.username = f"p-{self.phone.national_number}"
            else:
                self.username = self.email

        super().save(*args, **kwargs)

class ProfileAddesses(models.Model):
    profile = models.ForeignKey('Profile', on_delete=models.CASCADE)
    address = models.ForeignKey('address.UserAddress', on_delete=models.CASCADE)
    primary = models.BooleanField(_("Primary Address?"), default=False)
    shipping = models.BooleanField(_("Shipping Address?"), default=False)
    pickup = models.BooleanField(_("Pickup Address for Sellers"), default=False)

def upload_profile_photo_path(instance, filename):
    user = getattr(instance, 'user', None)
    if user == None:
        raise ValueError(_("Profile must be linked to existing user"))

    return f"profiles/users/{user.username}/{filename}"

class Profile(models.Model):
    TYPE_BUYER = 'B'
    TYPE_SELLER = 'S'
    TYPE_CEO = 'C'
    TYPE_CHOICES = (
        (TYPE_BUYER, _("Buyer")),
        (TYPE_SELLER, _("Seller")),
        (TYPE_CEO, _("CEO")),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, unique=True, blank=False, null=False, related_name='profile')
    type = models.CharField(_("User Profile Type"), name="type", max_length=4, db_index=True, choices=TYPE_CHOICES)
    level = models.PositiveSmallIntegerField(_("Seller or CEO level"), default=1)

    avatar_url = models.URLField(_("Avatar URL"), default='https://www.zite69.com/static/img/generic-profile.png')
    photo = models.ImageField(_("Profile Photo"), null=True, upload_to=upload_profile_photo_path)
    gstin = models.CharField(_("GSTIN Number"), name="gstin", max_length=15, db_index=True, blank=False, null=True, default=None, validators=[validate_length(15)])
    pan = INPANCardNumberField(_("PAN Number"), name="pan", max_length=10, db_index=True, blank=False, null=True, default=None)
    upi = models.CharField(_("UPI ID"), name="upi", max_length=45, db_index=True, blank=True, null=True, unique=True, validators=[validate_upi])
    tin = models.CharField(_("TIN Number"), name="tin", max_length=11, db_index=True, blank=True, null=True, unique=True, validators=[validate_length(11)])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['gstin'],
                condition=~models.Q(gstin='') & models.Q(gstin__isnull=False),
                name='unique_profile_gstin_ifnotnull'
                ),
            models.UniqueConstraint(
                fields=['pan'],
                condition=~models.Q(pan='') & models.Q(pan__isnull=False),
                name='unique_pan_inprofile_ifnotnull'
            )
        ]


    def get_type(self):
        for k, v in self.TYPE_CHOICES:
            if k == self.type:
                return v

        return ""
