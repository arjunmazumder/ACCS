<<<<<<< HEAD
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from lookup.models import Lookup
from vendors.models import City, ShopProfile
from products.models import Category, Product
from wallets.models import Wallet
from orders.models import DeliveryCharge
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds initial demo users, merchants, categories, and marketplace products matching the Next.js frontend requirements"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding demo marketplace data..."))

        # 1. Lookup roles
        vendor_role, _ = Lookup.objects.get_or_create(name='ROLE', value='VENDOR', defaults={'is_active': True})
        buyer_role, _ = Lookup.objects.get_or_create(name='ROLE', value='BUYER', defaults={'is_active': True})
        admin_role, _ = Lookup.objects.get_or_create(name='ROLE', value='ADMIN', defaults={'is_active': True})

        # 2. Users (Admin, Buyer, Vendors)
        admin_user, _ = User.objects.get_or_create(
            phone_number='01700000001',
            defaults={
                'full_name': 'Platform Super Admin',
                'is_staff': True,
                'is_superuser': True,
                'is_approved': True,
                'is_phone_verified': True
            }
        )
        admin_user.set_password('12345678')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        buyer_user, _ = User.objects.get_or_create(
            phone_number='01711111111',
            defaults={
                'full_name': 'Rahim Customer',
                'role': buyer_role,
                'is_staff': False,
                'is_superuser': False,
                'is_approved': True,
                'is_phone_verified': True
            }
        )
        buyer_user.set_password('12345678')
        buyer_user.role = buyer_role
        buyer_user.is_approved = True
        buyer_user.is_phone_verified = True
        buyer_user.save()

        vendor1, _ = User.objects.get_or_create(
            phone_number='01722222222',
            defaults={
                'full_name': 'Karim Gadgets',
                'role': vendor_role,
                'is_staff': False,
                'is_superuser': False,
                'is_approved': True,
                'is_phone_verified': True
            }
        )
        vendor1.set_password('12345678')
        vendor1.role = vendor_role
        vendor1.is_approved = True
        vendor1.is_phone_verified = True
        vendor1.save()

        vendor2, _ = User.objects.get_or_create(
            phone_number='01733333333',
            defaults={
                'full_name': 'Jamal Wholesale Hub',
                'role': vendor_role,
                'is_staff': False,
                'is_superuser': False,
                'is_approved': True,
                'is_phone_verified': True
            }
        )
        vendor2.set_password('12345678')
        vendor2.role = vendor_role
        vendor2.is_approved = True
        vendor2.is_phone_verified = True
        vendor2.save()

        # Update existing test users too
        for phone in ['01747727132', '01958480342']:
            u = User.objects.filter(phone_number=phone).first()
            if u:
                u.set_password('12345678')
                u.save()

        # 3. Cities
        dhaka, _ = City.objects.get_or_create(name='Dhaka', defaults={'is_active': True})
        ctg, _ = City.objects.get_or_create(name='Chattogram', defaults={'is_active': True})
        sylhet, _ = City.objects.get_or_create(name='Sylhet', defaults={'is_active': True})

        # 4. Merchant Shop Profiles
        shop1, _ = ShopProfile.objects.get_or_create(
            user=vendor1,
            defaults={
                'shop_name': 'Gadget World',
                'shop_type': 'RETAILER',
                'city': dhaka,
                'shop_address': 'Shop 4B, Multiplan Center, Elephant Road, Dhaka',
                'description': 'Premium computer peripherals, smart gadgets, and gaming gear.',
                'pathao_store_id': '10025',
                'average_rating': 4.9,
                'total_reviews': 28,
                'is_blocked': False
            }
        )

        shop2, _ = ShopProfile.objects.get_or_create(
            user=vendor2,
            defaults={
                'shop_name': 'Apex Wholesale Distro',
                'shop_type': 'WHOLESALER',
                'city': dhaka,
                'shop_address': 'Plot 15, Tejgaon Industrial Area, Dhaka',
                'description': 'Direct distributor for bulk electronics, chargers, and cables.',
                'pathao_store_id': '10048',
                'average_rating': 4.7,
                'total_reviews': 16,
                'is_blocked': False
            }
        )

        # 5. Wallets
        Wallet.objects.get_or_create(user=vendor1, defaults={'balance': Decimal('0.00'), 'credit_limit': Decimal('2000.00')})
        Wallet.objects.get_or_create(user=vendor2, defaults={'balance': Decimal('0.00'), 'credit_limit': Decimal('2000.00')})

        # 6. Categories
        cat_elec, _ = Category.objects.get_or_create(name='Electronics', defaults={'description': 'Consumer electronics and smart devices'})
        cat_comp, _ = Category.objects.get_or_create(name='Computers & Accessories', defaults={'parent': cat_elec, 'description': 'Mice, keyboards, and PC hardware'})
        cat_mob, _ = Category.objects.get_or_create(name='Mobile & Gadgets', defaults={'parent': cat_elec, 'description': 'Cables, chargers, and phone accessories'})
        cat_books, _ = Category.objects.get_or_create(name='Books & Media', defaults={'description': 'Educational books and literature'})

        # 7. Products
        demo_products = [
            {
                'title': 'Logitech MX Master 3S Wireless Mouse',
                'category': cat_comp,
                'shop': shop1,
                'price': Decimal('9500.00'),
                'discount_type': 'FLAT',
                'discount_value': Decimal('500.00'),
                'stock_quantity': 35,
                'moq': 1,
                'woner_commission': Decimal('8.00'),
                'low_stock_threshold': 5,
                'approval_status': 'APPROVED',
                'is_active': True,
                'description': 'Ergonomic performance wireless mouse with 8K DPI sensor and quiet clicks.'
            },
            {
                'title': 'Mechanical RGB Hot-Swap Keyboard',
                'category': cat_comp,
                'shop': shop1,
                'price': Decimal('4200.00'),
                'discount_type': 'PERCENTAGE',
                'discount_value': Decimal('10.00'),
                'stock_quantity': 18,
                'moq': 1,
                'woner_commission': Decimal('10.00'),
                'low_stock_threshold': 5,
                'approval_status': 'APPROVED',
                'is_active': True,
                'description': 'Custom mechanical keyboard with pre-lubed switches and hot-swappable PCB.'
            },
            {
                'title': 'Active Noise Cancelling Wireless Headphones',
                'category': cat_elec,
                'shop': shop1,
                'price': Decimal('5500.00'),
                'discount_type': 'NONE',
                'stock_quantity': 3,  # Triggers low stock alert!
                'moq': 1,
                'woner_commission': Decimal('10.00'),
                'low_stock_threshold': 5,
                'approval_status': 'APPROVED',
                'is_active': True,
                'description': 'Over-ear Bluetooth headphones with hybrid ANC and 40-hour battery life.'
            },
            {
                'title': 'Bulk 65W GaN Fast Chargers (Carton of 20)',
                'category': cat_mob,
                'shop': shop2,
                'price': Decimal('22000.00'),
                'discount_type': 'NONE',
                'stock_quantity': 12,
                'moq': 1,
                'woner_commission': Decimal('5.00'),
                'low_stock_threshold': 2,
                'approval_status': 'APPROVED',
                'is_active': True,
                'description': 'Wholesale pack of compact 65W GaN dual-port USB-C fast chargers.'
            },
        ]

        for p_data in demo_products:
            p, created = Product.objects.get_or_create(
                title=p_data['title'],
                shop=p_data['shop'],
                defaults=p_data
            )
            if not created:
                for k, v in p_data.items():
                    setattr(p, k, v)
                p.save()

        # 8. Delivery Charge
        deliv, _ = DeliveryCharge.objects.get_or_create(
            id=1,
            defaults={
                'inside_city': Decimal('60.00'),
                'outside_city': Decimal('120.00'),
                'hub_name': 'Central Warehouse Tejgaon',
                'hub_address': 'Tejgaon Central Consolidation Hub, Dhaka',
                'hub_phone': '01700000001',
                'hub_city': dhaka,
                'pathao_hub_store_id': 'HUB-TEJGAON-01'
            }
        )

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully!"))
        self.stdout.write(self.style.SUCCESS("""
Accounts configured:
  - Admin:  01700000001 / 12345678 (Sign in at /admin/login)
  - Buyer:  01711111111 / 12345678 (Sign in at /login)
  - Vendor: 01722222222 / 12345678 (Gadget World)
  - Vendor: 01733333333 / 12345678 (Apex Wholesale Distro)
"""))
=======
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
>>>>>>> d3f86bdf3dac8fc402d56ff1ebace7e1271c6a92
