from django.conf import settings
from django.contrib.sites.models import Site
from django.utils.text import slugify
from shop.apps.main.models import State, Postoffice
from shop.apps.seller.models import Seller
from shop.apps.user.models import User
from localflavor.in_.in_states import STATE_CHOICES
import string, random
import csv
import gzip

MAP_TO_STATE = {
    'Daman and Diu': 'Dadra and Nagar Haveli and Daman and Diu',
    'Pondicherry': 'Puducherry',
    'Andaman and Nico.In.': 'Andaman and Nicobar Islands',
    'Dadra and Nagar Hav.': 'Dadra and Nagar Haveli and Daman and Diu',
    'Chattisgarh': 'Chhattisgarh',
    'Megalaya': 'Meghalaya'
}

def generate_password(length=10):
    #Generate a random password of specified length after remvoing confusing characters
    #like l and O and 0 and 1
    characters = string.ascii_letters.replace('l', '').replace('O', '') + string.digits.replace('0', '').replace('1', '')
    return "".join(random.choice(characters) for i in range(length))

def run(*args):
    # Populate State and Postoffice tables
    for k, v in STATE_CHOICES:
        State.objects.get_or_create(code=k, defaults={'name': v})

    with gzip.open(settings.BASE_DIR / 'data/Pincode_30052019.csv.gz', 'rt', encoding='windows-1252') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            try:
                state = State.objects.get(name=MAP_TO_STATE.get(row[-1], row[-1]))
            except State.DoesNotExist:
                print(f"Unable to find state: {row[-1]}")
                continue
            Postoffice.objects.create(office=row[3], pincode=row[4],state=state)
    # Create the two Sites for our multi-site install
    try:
        main_site = Site.objects.get(pk=settings.DEFAULT_SITE_ID)
        main_site.domain = settings.ZITE69_MAIN_DOMAIN
        main_site.name = settings.ZITE69_MAIN_DOMAIN_NAME + ('-dev' if settings.DEBUG else '')
        main_site.save()
    except Site.DoesNotExist:
        main_site = Site.objects.create(
            domain = settings.ZITE69_MAIN_DOMAIN,
            name = settings.ZITE69_MAIN_DOMAIN_NAME + ('-dev' if settings.DEBUG else '')
        )

    try:
        seller_site = Site.objects.get(pk=settings.SELLER_SITE_ID)
        seller_site.domain = settings.ZITE69_SELLER_DOMAIN
        seller_site.name = settings.ZITE69_SELLER_DOMAIN_NAME + ('-dev' if settings.DEBUG else '')
        seller_site.save()
    except Site.DoesNotExist:
        seller_site = Site.objects.create(
            domain = settings.ZITE69_SELLER_DOMAIN,
            name = settings.ZITE69_SELLER_DOMAIN_NAME + ('-dev' if settings.DEBUG else '')
        )

    # Create main system user under who's account the main Seller account is created.
    sys_pass = generate_password()
    sys_user = User.objects.create_superuser(username=settings.ZITE69_MAIN_USERNAME, password=sys_pass, first_name='System', last_name='User') 
    with open(settings.BASE_DIR / "local/password.txt", "w") as f:
        f.write(sys_pass)

    # Create Main Seller
    Seller.objects.create(
            name = settings.ZITE69_MAIN_SELLER,
            handle = slugify(settings.ZITE69_MAIN_SELLER)[:20],
            user = sys_user
            )
