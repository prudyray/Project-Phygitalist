from shop.apps.user.models import User
from shop.apps.seller.models import Seller
import random
import string

def run(*args):
    buyers = []
    with open("./local/buyer-credentials.csv") as f:
        buyers = f.readlines()

    sellers = []
    with open("./local/seller-credentials.csv") as fs:
        sellers = fs.readlines()

    for buyer in buyers[1:]:
        username, password = buyer.split(",")
        password = password.rstrip("\n")
        
        try:
            user = User.objects.get(username=username)
            user.delete()
        except User.DoesNotExist:
            pass
        user = User.objects.create_user(
            username,
            password=password,
            )
        user.save()

    idx = 1
    for seller in sellers[1:]:
        username, password = seller.split(",")
        password = password.rstrip("\n")

        try:
            user = User.objects.get(username=username)
            try:
                seller = Seller.objects.get(user=user)
                seller.delete()
            except Seller.DoesNotExist as e:
                pass
            user.delete()
        except User.DoesNotExist:
            pass

        user = User.objects.create_user(
            username,
            password=password,
            is_staff=True,
            )
        user.save()

        seller, _ = Seller.objects.get_or_create(
            name = f"Seller-{idx}",
            handle = f"seller-{idx}",
            user = user,
            gstin = ''.join(random.choices(string.ascii_uppercase + string.digits, k=15)),
            gstin_verified = True,
            approved = True
            )
        
        seller.save()
        idx += 1
