"""
Default permissions for every role (Django Group).

Customer roles  (buyer, vendor, retailer, wholesaler, service_provider) mirror the account type
                users get at sign-up. Their screens are protected by role checks; these permissions
                document and back up what each account type may do.
Staff roles     (Order manager, Accountant, …) are ready-made roles for the admin team. A staff
                member only sees the admin pages their roles allow (see users.permissions).

Superusers and ADMIN-role users always have every permission.
"""
from django.contrib.auth.models import Group, Permission
from django.db import transaction


def crud(model, *actions):
    """'orders.order' -> ['orders.view_order', 'orders.add_order', ...] (all four by default)."""
    app, name = model.split('.')
    return [f'{app}.{a}_{name}' for a in (actions or ('view', 'add', 'change', 'delete'))]


VIEW = ('view',)
VIEW_CHANGE = ('view', 'change')

# ---------------- Customer roles ----------------
BUYER = [
    *crud('products.product', *VIEW), *crud('products.category', *VIEW),
    *crud('products.productreview', 'view', 'add', 'change'),
    *crud('products.wishlistitem'),
    *crud('orders.cart'), *crud('orders.cartitem'),
    *crud('orders.order', 'view', 'add'), *crud('orders.orderitem', *VIEW),
    *crud('users.shippingaddress'),
    *crud('vendors.shopprofile', *VIEW), *crud('vendors.shopreview', 'view', 'add', 'change'),
    *crud('vendors.city', *VIEW),
    *crud('core.policy', *VIEW), *crud('core.aboutus', *VIEW),
    *crud('marketing.banner', *VIEW), *crud('marketing.landingpage', *VIEW),
]

VENDOR = [
    *BUYER,
    *crud('products.product', 'add', 'change', 'delete'),
    'products.can_post_product', 'products.can_set_discount',   # not auto-approval: that is granted per shop
    *crud('products.productimage'),
    *crud('orders.vendororder', *VIEW_CHANGE),
    *crud('orders.ordercommission', *VIEW),
    *crud('vendors.shopprofile', *VIEW_CHANGE),
    *crud('wallets.wallet', *VIEW), *crud('wallets.wallettransaction', *VIEW),
    *crud('users.kycprofile', 'view', 'add', 'change'),
]

SERVICE_PROVIDER = [
    *BUYER,
    *crud('orders.vendororder', *VIEW),
    *crud('users.kycprofile', 'view', 'add', 'change'),
]

CUSTOMER_ROLES = {
    'buyer': BUYER,
    'vendor': VENDOR,
    'retailer': VENDOR,
    'wholesaler': VENDOR,
    'service_provider': SERVICE_PROVIDER,
}

# ---------------- Staff roles ----------------
STAFF_ROLES = {
    'Order manager': [
        *crud('orders.order', *VIEW_CHANGE), *crud('orders.orderitem', *VIEW_CHANGE), *crud('orders.vendororder', *VIEW_CHANGE),
        *crud('orders.cart', *VIEW), *crud('products.product', *VIEW), *crud('vendors.shopprofile', *VIEW),
        *crud('users.user', *VIEW), *crud('users.shippingaddress', *VIEW), *crud('vendors.city', *VIEW),
    ],
    'Product manager': [
        *crud('products.product'), 'products.can_post_product', 'products.can_set_discount', 'products.can_auto_approve_product',
        *crud('products.productimage'), *crud('products.category'),
        *crud('products.productreview', 'view', 'change', 'delete'), *crud('vendors.shopprofile', *VIEW),
    ],
    'Vendor manager': [
        *crud('vendors.shopprofile', *VIEW_CHANGE), *crud('vendors.shopreview', 'view', 'change', 'delete'),
        *crud('users.user', *VIEW_CHANGE), *crud('users.kycprofile', *VIEW_CHANGE),
        *crud('wallets.wallet', *VIEW_CHANGE), *crud('wallets.wallettransaction', *VIEW),
        *crud('orders.ordercommission', *VIEW), *crud('orders.vendororder', *VIEW), *crud('products.product', *VIEW),
    ],
    'Customer support': [
        *crud('orders.order', *VIEW_CHANGE), *crud('orders.orderitem', *VIEW), *crud('orders.vendororder', *VIEW),
        *crud('users.user', *VIEW), *crud('users.shippingaddress', *VIEW), *crud('users.kycprofile', *VIEW),
        *crud('products.product', *VIEW), *crud('products.productreview', *VIEW_CHANGE),
        *crud('vendors.shopprofile', *VIEW), *crud('vendors.shopreview', *VIEW_CHANGE),
    ],
    'Accountant': [
        *crud('finance.ledgerentry'), *crud('finance.financesettings', *VIEW_CHANGE),
        *crud('orders.order', *VIEW), *crud('orders.orderitem', *VIEW), *crud('orders.vendororder', *VIEW),
        *crud('orders.ordercommission', *VIEW), *crud('wallets.wallet', *VIEW), *crud('wallets.wallettransaction', *VIEW),
        *crud('vendors.shopprofile', *VIEW),
    ],
    'Marketing manager': [
        *crud('marketing.banner'), *crud('marketing.coupon'), *crud('marketing.landingpage'), *crud('marketing.landingpageitem'),
        *crud('marketing.sitesettings', *VIEW_CHANGE), *crud('core.broadcastannouncement'),
        *crud('core.policy', *VIEW_CHANGE), *crud('core.aboutus', *VIEW_CHANGE),
        *crud('products.product', *VIEW), *crud('products.category', *VIEW),
    ],
}

DEFAULT_ROLES = {**CUSTOMER_ROLES, **STAFF_ROLES}


def _permissions(names):
    perms = []
    for name in dict.fromkeys(names):
        app, codename = name.split('.')
        perm = Permission.objects.filter(content_type__app_label=app, codename=codename).first()
        if perm:
            perms.append(perm)
    return perms


@transaction.atomic
def setup_default_roles(reset=False, stdout=None):
    """
    Create the default roles. New roles get their default permissions. With `reset`, existing default
    roles are set back to exactly their defaults (roles made by the admin are never touched).
    """
    for name, names in DEFAULT_ROLES.items():
        group, created = Group.objects.get_or_create(name=name)
        if created or reset:
            perms = _permissions(names)
            group.permissions.set(perms)
            if stdout:
                stdout.write(f"{'Created' if created else 'Reset'} role '{name}' with {len(perms)} permissions")
