"""
Seed the database with demo data so the frontend can be exercised end-to-end.

    python manage.py seed_demo

Idempotent: running it again only fills in what is missing.

Demo accounts (password for all: 12345678):
    Admin   01700000001
    Buyer   01711111111
    Vendor  01722222222  (Retailer  - Dhaka Fashion House)
    Vendor  01733333333  (Wholesaler - Chattogram Electronics Hub)
"""
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import AboutUs, Policy
from lookup.models import Lookup
from orders.models import DeliveryCharge
from products.models import Category, Product
from users.models import KYCProfile, User
from vendors.models import City, ShopProfile
from wallets.models import Wallet

DEMO_PASSWORD = '12345678'

ROLES = ['BUYER', 'VENDOR', 'RETAILER', 'WHOLESALER', 'ADMIN', 'SERVICE_PROVIDER']
CITIES = ['Dhaka', 'Chattogram', 'Sylhet', 'Rajshahi', 'Khulna', 'Barishal', 'Rangpur', 'Mymensingh']

CATEGORY_TREE = {
    'Fashion': ["Men's Clothing", "Women's Clothing", 'Footwear'],
    'Electronics': ['Mobile Phones', 'Accessories', 'Audio'],
    'Home & Living': ['Kitchen', 'Decor', 'Furniture'],
    'Groceries': ['Rice & Grains', 'Spices', 'Beverages'],
    'Health & Beauty': ['Skin Care', 'Personal Care'],
}

SHOPS = [
    {
        'phone': '01722222222', 'name': 'Rahim Uddin', 'role': 'RETAILER',
        'shop_name': 'Dhaka Fashion House', 'shop_type': 'RETAILER', 'city': 'Dhaka',
        'address': 'House 12, Road 5, Dhanmondi, Dhaka 1205', 'email': 'hello@dhakafashion.test',
        'description': 'Trendy apparel and footwear curated for everyday Bangladeshi style.',
        'products': [
            ("Men's Cotton Panjabi", "Men's Clothing", 'L', 1850, 40, 1, 'PERCENTAGE', 10, 5),
            ("Classic Oxford Shirt", "Men's Clothing", 'M', 1250, 60, 1, 'NONE', None, 5),
            ("Women's Printed Kurti", "Women's Clothing", 'M', 1450, 35, 1, 'FLAT', 200, 5),
            ("Handloom Cotton Saree", "Women's Clothing", 'Free', 3200, 12, 1, 'NONE', None, 6),
            ("Leather Loafers", 'Footwear', '42', 2600, 3, 1, 'PERCENTAGE', 15, 5),
            ("Everyday Sneakers", 'Footwear', '41', 2200, 25, 1, 'NONE', None, 5),
        ],
    },
    {
        'phone': '01733333333', 'name': 'Karim Hossain', 'role': 'WHOLESALER',
        'shop_name': 'Chattogram Electronics Hub', 'shop_type': 'WHOLESALER', 'city': 'Chattogram',
        'address': 'Shop 44, Reazuddin Bazar, Chattogram 4000', 'email': 'sales@ctgelectronics.test',
        'description': 'Wholesale and retail electronics, gadgets and accessories at the best price.',
        'products': [
            ('Wireless Earbuds Pro', 'Audio', None, 2490, 80, 2, 'PERCENTAGE', 12, 4),
            ('Bluetooth Speaker Mini', 'Audio', None, 1790, 50, 1, 'NONE', None, 4),
            ('20W Fast Charger', 'Accessories', None, 890, 150, 5, 'FLAT', 90, 3),
            ('Braided USB-C Cable (1m)', 'Accessories', None, 350, 300, 10, 'NONE', None, 3),
            ('Smartphone X12 (8/128GB)', 'Mobile Phones', None, 21990, 15, 1, 'PERCENTAGE', 5, 3),
            ('Power Bank 10000mAh', 'Accessories', None, 1590, 4, 1, 'NONE', None, 3),
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed demo roles, cities, categories, shops, products and demo accounts.'

    @transaction.atomic
    def handle(self, *args, **options):
        roles = {value: Lookup.objects.get_or_create(name='ROLE', value=value, defaults={'is_active': True})[0] for value in ROLES}
        cities = {name: City.objects.get_or_create(name=name)[0] for name in CITIES}

        if not DeliveryCharge.objects.exists():
            DeliveryCharge.objects.create(
                inside_city=Decimal('60'), outside_city=Decimal('120'),
                hub_name='ACCS Central Warehouse', hub_address='Tejgaon Industrial Area, Dhaka 1208',
                hub_phone='01700000000', hub_city=cities['Dhaka'],
            )

        categories = {}
        for parent_name, children in CATEGORY_TREE.items():
            parent, _ = Category.objects.get_or_create(name=parent_name, parent=None)
            categories[parent_name] = parent
            for child_name in children:
                categories[child_name], _ = Category.objects.get_or_create(name=child_name, parent=parent)

        # Accounts
        admin = self._user('01700000001', 'ACCS Admin', roles['ADMIN'], is_staff=True)
        self._user('01711111111', 'Demo Buyer', roles['BUYER'], group='buyer')

        for spec in SHOPS:
            vendor = self._user(spec['phone'], spec['name'], roles[spec['role']], group=spec['role'].lower())
            KYCProfile.objects.get_or_create(
                user=vendor,
                defaults={'nid_number': '19900000000' + spec['phone'][-2:], 'status': 'APPROVED', 'verified_at': timezone.now()},
            )
            Wallet.objects.get_or_create(user=vendor)
            shop, _ = ShopProfile.objects.get_or_create(
                user=vendor,
                defaults={
                    'shop_name': spec['shop_name'], 'shop_type': spec['shop_type'], 'city': cities[spec['city']],
                    'shop_address': spec['address'], 'contact_email': spec['email'], 'description': spec['description'],
                },
            )
            for title, cat, size, price, stock, moq, d_type, d_value, commission in spec['products']:
                Product.objects.get_or_create(
                    shop=shop, title=title,
                    defaults={
                        'category': categories[cat], 'size': size, 'price': Decimal(price), 'stock_quantity': stock,
                        'moq': moq, 'discount_type': d_type, 'discount_value': Decimal(d_value) if d_value else None,
                        'woner_commission': Decimal(commission), 'approval_status': 'APPROVED', 'is_active': True,
                        'description': f'{title} from {spec["shop_name"]}. Quality checked, genuine product with fast delivery across Bangladesh.',
                    },
                )

        if not Policy.objects.exists():
            Policy.objects.create(title='Return Policy', description='Items can be returned within 7 days of delivery if they are unused and in original packaging.')
            Policy.objects.create(title='Privacy Policy', description='We only use your phone number and address to process and deliver your orders.')
        if not AboutUs.objects.exists():
            AboutUs.objects.create(title='About ACCS', description='ACCS is a multi-vendor marketplace connecting Bangladeshi retailers and wholesalers with buyers nationwide, with courier delivery by Pathao.')

        self.stdout.write(self.style.SUCCESS(
            f'Demo data ready. Admin: {admin.phone_number} / {DEMO_PASSWORD}; '
            f'Buyer: 01711111111; Vendors: 01722222222, 01733333333 (password {DEMO_PASSWORD}).'
        ))

    def _user(self, phone, name, role, is_staff=False, group=None):
        user, created = User.objects.get_or_create(
            phone_number=phone,
            defaults={'full_name': name, 'role': role, 'is_staff': is_staff, 'is_approved': True, 'is_phone_verified': True},
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        if group:
            user.groups.add(Group.objects.get_or_create(name=group)[0])
        return user
