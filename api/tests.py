from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from lookup.models import Lookup
from orders.models import Cart, CartItem, Order
from products.models import Category, Product
from vendors.models import ShopProfile, ShopReview

User = get_user_model()


class FrontendSupportEndpointsTestCase(TestCase):
    """Endpoints added / hardened for the Next.js frontend."""

    def setUp(self):
        self.client = APIClient()
        buyer_role, _ = Lookup.objects.get_or_create(name='ROLE', value='BUYER')
        vendor_role, _ = Lookup.objects.get_or_create(name='ROLE', value='RETAILER')

        self.buyer = User.objects.create_user(phone_number='01811111111', password='password123', full_name='Buyer', role=buyer_role, is_phone_verified=True, is_approved=True)
        self.vendor = User.objects.create_user(phone_number='01822222222', password='password123', full_name='Vendor', role=vendor_role, is_phone_verified=True, is_approved=True)
        self.other_vendor = User.objects.create_user(phone_number='01833333333', password='password123', full_name='Other', role=vendor_role, is_phone_verified=True, is_approved=True)
        self.admin = User.objects.create_superuser(phone_number='01844444444', password='password123')

        self.shop = ShopProfile.objects.create(user=self.vendor, shop_name='Alpha', shop_address='Dhaka')
        self.other_shop = ShopProfile.objects.create(user=self.other_vendor, shop_name='Beta', shop_address='Dhaka')
        self.parent = Category.objects.create(name='Fashion')
        self.child = Category.objects.create(name='Shoes', parent=self.parent)
        self.product = Product.objects.create(
            shop=self.shop, category=self.child, title='Sneaker', price=Decimal('1000'), stock_quantity=10,
            approval_status='APPROVED', woner_commission=Decimal('5'),
        )
        self.pending_product = Product.objects.create(shop=self.shop, title='Draft', price=Decimal('50'), stock_quantity=1)

    def login(self, phone):
        res = self.client.post('/api/auth/login/', {'phone_number': phone, 'password': 'password123'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertIn('refresh_token', res.data['data'])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['data']['access_token']}")
        return res.data['data']

    def test_refresh_token_in_body_rotates(self):
        data = self.login('01811111111')
        self.client.cookies.clear()
        res = self.client.post('/api/auth/getRefreshToken/', {'refresh_token': data['refresh_token']}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertNotEqual(res.data['refresh_token'], data['refresh_token'])

    def test_me_get_and_update(self):
        self.login('01811111111')
        res = self.client.get('/api/auth/me/')
        self.assertEqual(res.data['user']['phone_number'], '01811111111')
        res = self.client.patch('/api/auth/me/', {'full_name': 'New Name'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['user']['full_name'], 'New Name')

    def test_change_password(self):
        self.login('01811111111')
        bad = self.client.post('/api/auth/change-password/', {'current_password': 'wrong', 'new_password': 'newpass1', 'confirm_new_password': 'newpass1'}, format='json')
        self.assertEqual(bad.status_code, 400)
        ok = self.client.post('/api/auth/change-password/', {'current_password': 'password123', 'new_password': 'newpass1', 'confirm_new_password': 'newpass1'}, format='json')
        self.assertEqual(ok.status_code, 200)
        self.buyer.refresh_from_db()
        self.assertTrue(self.buyer.check_password('newpass1'))

    def test_forgot_and_reset_password(self):
        res = self.client.post('/api/auth/forgot-password/', {'phone_number': '01811111111'}, format='json')
        self.assertEqual(res.status_code, 200)
        from users.models import OTPVerification
        otp = OTPVerification.objects.get(phone_number='01811111111').otp_code
        res = self.client.post('/api/auth/reset-password/', {
            'phone_number': '01811111111', 'otp_code': otp, 'new_password': 'reset123', 'confirm_new_password': 'reset123',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.buyer.refresh_from_db()
        self.assertTrue(self.buyer.check_password('reset123'))

    def test_only_admin_can_write_categories(self):
        self.login('01811111111')
        self.assertEqual(self.client.post('/api/products/categories', {'name': 'X'}, format='json').status_code, 403)
        self.login('01844444444')
        self.assertEqual(self.client.post('/api/products/categories', {'name': 'X'}, format='json').status_code, 201)

    def test_vendor_can_only_edit_own_products(self):
        self.login('01833333333')
        res = self.client.patch(f'/api/products/products/{self.product.id}', {'price': '1'}, format='json')
        self.assertEqual(res.status_code, 403)
        self.login('01822222222')
        res = self.client.patch(f'/api/products/products/{self.pending_product.id}', {'stock_quantity': 7}, format='json')
        self.assertEqual(res.status_code, 200)

    def test_vendor_cannot_set_commission(self):
        self.login('01822222222')
        self.client.patch(f'/api/products/products/{self.product.id}', {'woner_commission': '0'}, format='json')
        self.product.refresh_from_db()
        self.assertEqual(self.product.woner_commission, Decimal('5'))

    def test_rejected_product_edit_returns_to_review(self):
        self.pending_product.approval_status = 'REJECTED'
        self.pending_product.save()
        self.login('01822222222')
        self.client.patch(f'/api/products/products/{self.pending_product.id}', {'title': 'Fixed'}, format='json')
        self.pending_product.refresh_from_db()
        self.assertEqual(self.pending_product.approval_status, 'PENDING')

    def test_parent_category_filter_includes_children(self):
        res = self.client.get(f'/api/products/products?category={self.parent.id}')
        self.assertEqual([p['id'] for p in res.data['data']], [self.product.id])

    def test_review_is_saved_for_reviewer_once(self):
        self.login('01811111111')
        payload = {'shop': self.shop.id, 'product_rating': 4, 'price_rating': 4, 'on_time_delivery_rating': 4, 'response_and_behavior_rating': 4}
        self.assertEqual(self.client.post('/api/vendors/reviews', payload, format='json').status_code, 201)
        self.assertEqual(ShopReview.objects.get().reviewer, self.buyer)
        self.assertEqual(self.client.post('/api/vendors/reviews', payload, format='json').status_code, 400)

    def test_buyer_can_cancel_pending_order_only(self):
        order = Order.objects.create(buyer=self.buyer, shipping_address='Dhaka', contact_phone='01811111111')
        self.login('01811111111')
        res = self.client.post(f'/api/orders/buyer/orders/{order.id}/cancel/', {}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['status'], 'CANCELLED')
        res = self.client.post(f'/api/orders/buyer/orders/{order.id}/cancel/', {}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_vendor_dashboard_and_admin_delivery_settings(self):
        self.login('01822222222')
        res = self.client.get('/api/vendors/shops/me/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['products']['approved'], 1)
        self.assertEqual(self.client.get('/api/orders/admin/delivery-settings/').status_code, 403)
        self.login('01844444444')
        res = self.client.patch('/api/orders/admin/delivery-settings/', {'hub_name': 'Main Hub'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['hub_name'], 'Main Hub')

    def test_checkout_flow_from_cart(self):
        self.login('01811111111')
        cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2, unit_price=Decimal('1000'))
        res = self.client.post('/api/orders/buyer/orders/', {
            'shipping_address': 'House 1, Dhaka', 'contact_phone': '01811111111',
            'pathao_recipient_city_id': 1, 'pathao_recipient_zone_id': 101,
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['status'], 'PENDING_ADMIN_APPROVAL')
        self.assertFalse(cart.items.exists())


class StaffPermissionTestCase(TestCase):
    """Staff only reach admin APIs their role grants; superusers reach everything."""

    def setUp(self):
        from django.contrib.auth.models import Group, Permission
        self.client = APIClient()
        self.group = Group.objects.create(name='order manager')
        self.group.permissions.add(Permission.objects.get(codename='view_order'))
        self.staff = User.objects.create_user(phone_number='01855555555', password='password123', is_staff=True, is_approved=True, is_phone_verified=True)
        self.staff.groups.add(self.group)
        User.objects.create_superuser(phone_number='01866666666', password='password123')

    def login(self, phone):
        res = self.client.post('/api/admin/login/', {'phone_number': phone, 'password': 'password123'}, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['data']['access_token']}")
        return res.data['data']['user']['user']

    def test_staff_limited_to_granted_models(self):
        user = self.login('01855555555')
        self.assertIn('view_order', user['permissions'])
        self.assertEqual(self.client.get('/api/orders/admin/orders/').status_code, 200)
        self.assertEqual(self.client.get('/api/admin/dashboard/analytics/').status_code, 200)
        self.assertEqual(self.client.get('/api/wallets/admin/all/').status_code, 403)
        self.assertEqual(self.client.get('/api/auth/').status_code, 403)
        self.assertEqual(self.client.get('/api/orders/admin/orders/commissions/').status_code, 403)
        self.assertEqual(self.client.post('/api/products/categories', {'name': 'X'}, format='json').status_code, 403)

    def test_superuser_has_full_access(self):
        self.login('01866666666')
        self.assertEqual(self.client.get('/api/wallets/admin/all/').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/').status_code, 200)
        self.assertEqual(self.client.get('/api/orders/admin/orders/commissions/').status_code, 200)


class OTPLoginTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        User.objects.create_user(phone_number='01877777777', password='password123', is_approved=True, is_phone_verified=True)

    def test_otp_login_flow_and_single_use(self):
        from users.models import OTPVerification
        self.assertEqual(self.client.post('/api/auth/login-otp/', {'phone_number': '01899999999'}, format='json').status_code, 404)
        self.assertEqual(self.client.post('/api/auth/login-otp/', {'phone_number': '01877777777'}, format='json').status_code, 200)
        code = OTPVerification.objects.get(phone_number='01877777777').otp_code
        res = self.client.post('/api/auth/verify-otp/', {'phone_number': '01877777777', 'otp_code': code}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('access_token', res.data['data'])
        again = self.client.post('/api/auth/verify-otp/', {'phone_number': '01877777777', 'otp_code': code}, format='json')
        self.assertEqual(again.status_code, 400)

    def test_buyer_password_is_not_derived_from_phone(self):
        from users.models import OTPVerification
        self.client.post('/api/auth/buyer/register/', {'phone_number': '01888888888', 'full_name': 'New'}, format='json')
        code = OTPVerification.objects.get(phone_number='01888888888').otp_code
        self.client.post('/api/auth/buyer/register-verify/', {'phone_number': '01888888888', 'otp_code': code}, format='json')
        self.assertFalse(User.objects.get(phone_number='01888888888').check_password('888888'))
