from django.db.models.signals import post_save
from django.dispatch import receiver
from vendors.models import ShopProfile
from .models import Wallet

@receiver(post_save, sender=ShopProfile)
def create_wallet_for_shop_profile(sender, instance, created, **kwargs):
    if created and instance.user:
        Wallet.objects.get_or_create(user=instance.user)
