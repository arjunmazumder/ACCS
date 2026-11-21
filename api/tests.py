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


def finish_login_otp(client, path, phone, res):
    """Super admins get a code by SMS after the password; tests read it from the database."""
    if res.status_code == 200 and res.data.get('status') == 'otp_required':
        from users.models import OTPVerification
        code = OTPVerification.objects.get(phone_number=phone).otp_code
        res = client.post(path, {'phone_number': phone, 'password': 'password123', 'otp_code': code}, format='json')
    return res



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
        res = finish_login_otp(self.client, '/api/auth/login/', phone, res)
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

    def test_admin_creates_product_for_a_shop(self):
        self.login('01844444444')
        payload = {'title': 'Admin Book', 'category': self.child.id, 'price': '250', 'stock_quantity': 5, 'woner_commission': '7'}
        res = self.client.post('/api/products/products', payload, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('shop', res.data.get('errors', res.data) if isinstance(res.data, dict) else {})
        res = self.client.post('/api/products/products', {**payload, 'shop': 9999}, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.post('/api/products/products', {**payload, 'shop': self.other_shop.id}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        product = Product.objects.get(title='Admin Book')
        self.assertEqual(product.shop, self.other_shop)
        self.assertEqual(product.approval_status, 'APPROVED')
        self.assertEqual(product.woner_commission, Decimal('7'))

    def test_preview_pdf_upload_validation_and_removal(self):
        import shutil
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings

        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        pdf = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'
        url = f'/api/products/products/{self.product.id}'
        with override_settings(MEDIA_ROOT=media):
            self.login('01844444444')
            fake = SimpleUploadedFile('pages.pdf', b'not a pdf', content_type='application/pdf')
            self.assertEqual(self.client.patch(url, {'preview_pdf': fake}, format='multipart').status_code, 400)
            png = SimpleUploadedFile('pages.png', pdf, content_type='image/png')
            self.assertEqual(self.client.patch(url, {'preview_pdf': png}, format='multipart').status_code, 400)

            res = self.client.patch(url, {'preview_pdf': SimpleUploadedFile('pages.pdf', pdf, content_type='application/pdf')}, format='multipart')
            self.assertEqual(res.status_code, 200, res.data)
            self.product.refresh_from_db()
            self.assertTrue(self.product.preview_pdf.name.startswith('product_previews/'))
            self.client.credentials()
            public = self.client.get(url).data
            self.assertIn('/media/product_previews/', public.get('data', public)['preview_pdf'])

            self.login('01844444444')
            res = self.client.patch(url, {'preview_pdf': ''}, format='multipart')
            self.assertEqual(res.status_code, 200, res.data)
            self.product.refresh_from_db()
            self.assertFalse(self.product.preview_pdf)

    def test_nested_categories_filter_counts_and_depth(self):
        running = Category.objects.create(name='Running', parent=self.child)  # Fashion > Shoes > Running
        deep = Product.objects.create(shop=self.shop, category=running, title='Runner', price=Decimal('500'),
                                      stock_quantity=3, approval_status='APPROVED')
        ids = lambda res: sorted(p['id'] for p in res.data['data'])  # noqa: E731
        self.assertEqual(ids(self.client.get(f'/api/products/products?category={self.parent.id}')), sorted([self.product.id, deep.id]))
        self.assertEqual(ids(self.client.get(f'/api/products/products?category={running.id}')), [deep.id])

        counts = {c['id']: c['count'] for c in self.client.get('/api/products/products/facets').data['categories']}
        self.assertEqual((counts[self.parent.id], counts[self.child.id], counts[running.id]), (2, 2, 1))

        detail = self.client.get(f'/api/products/products/{deep.id}').data
        detail = detail.get('data', detail)
        self.assertEqual([a['name'] for a in detail['category_details']['ancestors']], ['Fashion', 'Shoes'])

        self.login('01844444444')
        too_deep = self.client.post('/api/products/categories', {'name': 'Trail', 'parent': running.id}, format='json')
        self.assertEqual(too_deep.status_code, 400)
        loop = self.client.patch(f'/api/products/categories/{self.parent.id}', {'parent': running.id}, format='json')
        self.assertEqual(loop.status_code, 400)

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
        res = finish_login_otp(self.client, '/api/admin/login/', phone, res)
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

    def test_staff_needs_product_permission_to_add_products(self):
        from django.contrib.auth.models import Permission
        vendor = User.objects.create_user(phone_number='01877777770', password='password123', is_approved=True)
        shop = ShopProfile.objects.create(user=vendor, shop_name='Gamma', shop_address='Dhaka')
        payload = {'title': 'Staff Book', 'price': '100', 'stock_quantity': 1, 'shop': shop.id}
        self.login('01855555555')
        self.assertEqual(self.client.post('/api/products/products', payload, format='json').status_code, 403)
        self.group.permissions.add(Permission.objects.get(codename='add_product'))
        self.assertEqual(self.client.post('/api/products/products', payload, format='json').status_code, 201)

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


class BookCatalogueTestCase(TestCase):
    """Class/subject tree ordering, multi-value filters, facets and home sections."""

    def setUp(self):
        self.client = APIClient()
        seller = User.objects.create_user(phone_number='01891111111', password='password123', is_approved=True, is_phone_verified=True)
        shop = ShopProfile.objects.create(user=seller, shop_name='Books', shop_address='Dhaka')
        self.class2 = Category.objects.create(name='Class 2', position=2)
        self.class10 = Category.objects.create(name='Class 10', position=10)
        self.math2 = Category.objects.create(name='Mathematics', parent=self.class2, position=1)
        self.physics10 = Category.objects.create(name='Physics', parent=self.class10, position=1)

        def book(title, cat, publisher, author, **extra):
            return Product.objects.create(shop=shop, category=cat, title=title, publisher=publisher, author=author,
                                          price=Decimal('100'), stock_quantity=5, approval_status='APPROVED', **extra)

        book('Math 2', self.math2, 'Alpha Press', 'Rina')
        book('Physics 10', self.physics10, 'Beta Press', 'Karim', discount_type='PERCENTAGE', discount_value=Decimal('10'))
        book('Hidden', self.physics10, 'Alpha Press', 'Rina', is_active=False)

    def test_tree_is_ordered_by_position(self):
        names = [c['name'] for c in self.client.get('/api/products/categories/tree').data]
        self.assertEqual(names, ['Class 2', 'Class 10'])

    def test_multi_value_filters(self):
        res = self.client.get(f'/api/products/products?category={self.class2.id},{self.class10.id}')
        self.assertEqual(res.data['meta']['count'], 2)
        res = self.client.get('/api/products/products?publisher=Beta Press,Gamma')
        self.assertEqual([p['title'] for p in res.data['data']], ['Physics 10'])
        res = self.client.get('/api/products/products?discounted=1')
        self.assertEqual([p['title'] for p in res.data['data']], ['Physics 10'])
        res = self.client.get('/api/products/products?search=Karim')
        self.assertEqual(res.data['meta']['count'], 1)

    def test_facets_ignore_own_selection_and_hidden_books(self):
        res = self.client.get(f'/api/products/products/facets?category={self.class2.id}&publisher=Alpha Press')
        publishers = {p['value']: p['count'] for p in res.data['publishers']}
        self.assertEqual(publishers, {'Alpha Press': 1})  # inactive book not counted
        counts = {c['id']: c['count'] for c in res.data['categories']}
        self.assertEqual(counts[self.class2.id], 1)  # class total includes its subjects

    def test_home_sections_group_by_class(self):
        res = self.client.get('/api/products/products/home-sections?limit=5')
        self.assertEqual([s['category']['name'] for s in res.data], ['Class 2', 'Class 10'])
        self.assertEqual(res.data[1]['total'], 1)


class MarketingAndEngagementTestCase(TestCase):
    """Banners, landing pages (guest orders), coupons, wishlist and book reviews."""

    def setUp(self):
        from marketing.models import Coupon, LandingPage, LandingPageItem
        self.client = APIClient()
        seller = User.objects.create_user(phone_number='01892222222', password='password123', is_approved=True, is_phone_verified=True)
        shop = ShopProfile.objects.create(user=seller, shop_name='Books', shop_address='Dhaka')
        self.book = Product.objects.create(shop=shop, title='Physics Guide', price=Decimal('500'), stock_quantity=10, approval_status='APPROVED')
        self.other = Product.objects.create(shop=shop, title='Not in offer', price=Decimal('100'), stock_quantity=10, approval_status='APPROVED')
        self.page = LandingPage.objects.create(title='SSC Pack', slug='ssc-pack')
        LandingPageItem.objects.create(landing_page=self.page, product=self.book, is_preselected=True)
        Coupon.objects.create(code='save50', discount_type='FLAT', value=Decimal('50'), min_order_amount=Decimal('400'), usage_limit=1)
        User.objects.create_superuser(phone_number='01893333333', password='password123')

    def login(self, phone, path='/api/auth/login/'):
        res = self.client.post(path, {'phone_number': phone, 'password': 'password123'}, format='json')
        res = finish_login_otp(self.client, path, phone, res)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['data']['access_token']}")

    def test_guest_landing_order_creates_buyer_and_applies_coupon_once(self):
        payload = {'items': [{'product_id': self.book.id, 'quantity': 1}], 'full_name': 'Guest Buyer',
                   'phone_number': '01894444444', 'address': 'House 1, Dhaka', 'coupon_code': 'SAVE50'}
        res = self.client.post('/api/marketing/landing/ssc-pack/order/', payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data['account_created'])
        order = res.data['order']
        self.assertEqual(order['source'], 'LANDING')
        self.assertEqual(Decimal(str(order['discount_amount'])), Decimal('50'))
        self.assertEqual(Decimal(str(order['grand_total'])), Decimal('500') + Decimal(str(order['total_delivery_charge'])) - Decimal('50'))
        # usage limit reached
        payload['phone_number'] = '01895555555'
        self.assertEqual(self.client.post('/api/marketing/landing/ssc-pack/order/', payload, format='json').status_code, 400)

    def test_site_settings_public_read_admin_write(self):
        res = self.client.get('/api/marketing/site-settings/')
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data['whatsapp_url'])
        self.assertEqual(self.client.patch('/api/marketing/site-settings/', {'whatsapp_number': '01712345678'}, format='json').status_code, 401)
        self.login('01892222222')
        self.assertEqual(self.client.patch('/api/marketing/site-settings/', {'whatsapp_number': '01712345678'}, format='json').status_code, 403)
        self.login('01893333333', '/api/admin/login/')
        res = self.client.patch('/api/marketing/site-settings/', {'whatsapp_number': '017-1234 5678', 'whatsapp_message': 'Hi there'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['whatsapp_number'], '8801712345678')
        self.assertEqual(res.data['whatsapp_url'], 'https://wa.me/8801712345678?text=Hi%20there')
        self.assertEqual(self.client.patch('/api/marketing/site-settings/', {'whatsapp_number': '123'}, format='json').status_code, 400)

    def test_landing_order_rejects_products_outside_the_page(self):
        payload = {'items': [{'product_id': self.other.id, 'quantity': 1}], 'full_name': 'X',
                   'phone_number': '01896666666', 'address': 'Dhaka'}
        self.assertEqual(self.client.post('/api/marketing/landing/ssc-pack/order/', payload, format='json').status_code, 400)

    def test_admin_manages_landing_pages_and_banners(self):
        self.assertEqual(self.client.get('/api/marketing/landing-pages/').status_code, 401)
        self.login('01893333333', '/api/admin/login/')
        res = self.client.post('/api/marketing/landing-pages/', {'title': 'Eid Offer', 'product_ids': [self.other.id, self.book.id],
                                                                 'preselected_ids': [self.book.id]}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['slug'], 'eid-offer')
        self.assertEqual([i['product']['id'] for i in res.data['items']], [self.other.id, self.book.id])
        self.assertEqual(self.client.get('/api/marketing/landing/eid-offer/').status_code, 200)
        self.assertEqual(self.client.get('/api/marketing/banners/').status_code, 200)

    def test_coupon_validation(self):
        res = self.client.post('/api/marketing/coupons/validate/', {'code': 'SAVE50', 'subtotal': '300'}, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.post('/api/marketing/coupons/validate/', {'code': 'save50', 'subtotal': '450'}, format='json')
        self.assertEqual(Decimal(str(res.data['discount'])), Decimal('50'))

    def test_wishlist_and_reviews_require_purchase(self):
        buyer = User.objects.create_user(phone_number='01897777777', password='password123', is_approved=True, is_phone_verified=True)
        self.login('01897777777')
        self.client.post('/api/products/wishlist', {'product_id': self.book.id}, format='json')
        self.assertEqual(self.client.get('/api/products/wishlist').data['ids'], [self.book.id])
        review = {'product': self.book.id, 'rating': 5, 'comment': 'Great'}
        self.assertEqual(self.client.post('/api/products/reviews', review, format='json').status_code, 403)
        from orders.models import Order, OrderItem
        order = Order.objects.create(buyer=buyer, shipping_address='Dhaka', contact_phone='01897777777', status='DELIVERED')
        OrderItem.objects.create(order=order, product=self.book, shop=self.book.shop, quantity=1, unit_price=Decimal('500'))
        self.assertEqual(self.client.post('/api/products/reviews', review, format='json').status_code, 201)
        self.book.refresh_from_db()
        self.assertEqual((self.book.rating_avg, self.book.rating_count), (5.0, 1))


class SuperAdminLoginOTPTestCase(TestCase):
    """Super admins sign in with password + a code sent by SMS; everyone else with just a password."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient()
        buyer_role, _ = Lookup.objects.get_or_create(name='ROLE', value='BUYER')
        self.buyer = User.objects.create_user(phone_number='01811112222', password='password123', role=buyer_role, is_phone_verified=True, is_approved=True)
        self.staff = User.objects.create_user(phone_number='01811113333', password='password123', is_staff=True, is_phone_verified=True, is_approved=True)
        self.admin = User.objects.create_superuser(phone_number='01811114444', password='password123')

    def post(self, url, **data):
        return self.client.post(url, {'phone_number': self.admin.phone_number, 'password': 'password123', **data}, format='json')

    def code(self):
        from users.models import OTPVerification
        return OTPVerification.objects.get(phone_number=self.admin.phone_number).otp_code

    def test_buyer_and_staff_need_no_code(self):
        res = self.client.post('/api/auth/login/', {'phone_number': self.buyer.phone_number, 'password': 'password123'}, format='json')
        self.assertIn('access_token', res.data['data'])
        res = self.client.post('/api/admin/login/', {'phone_number': self.staff.phone_number, 'password': 'password123'}, format='json')
        self.assertIn('access_token', res.data['data'])

    def test_super_admin_needs_code_on_both_login_endpoints(self):
        for url in ('/api/admin/login/', '/api/auth/login/'):
            res = self.post(url)
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data['status'], 'otp_required')
            self.assertNotIn('access_token', str(res.data))
            self.assertNotIn('access_token', res.cookies)
            res = self.post(url, otp_code=self.code())
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertIn('access_token', res.data['data'])

    def test_wrong_password_sends_no_code(self):
        res = self.client.post('/api/admin/login/', {'phone_number': self.admin.phone_number, 'password': 'nope'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        from users.models import OTPVerification
        self.assertFalse(OTPVerification.objects.filter(phone_number=self.admin.phone_number).exists())

    def test_code_needs_the_password_too(self):
        self.post('/api/admin/login/')
        res = self.client.post('/api/admin/login/', {'phone_number': self.admin.phone_number, 'password': 'nope', 'otp_code': self.code()}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wrong_code_and_reuse_are_rejected(self):
        self.post('/api/admin/login/')
        good = self.code()
        bad = '000000' if good != '000000' else '111111'
        self.assertEqual(self.post('/api/admin/login/', otp_code=bad).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.post('/api/admin/login/', otp_code=good).status_code, status.HTTP_200_OK)
        self.assertEqual(self.post('/api/admin/login/', otp_code=good).status_code, status.HTTP_400_BAD_REQUEST)

    def test_too_many_wrong_codes_burn_the_code(self):
        self.post('/api/admin/login/')
        good = self.code()
        bad = '000000' if good != '000000' else '111111'
        for _ in range(5):
            self.post('/api/admin/login/', otp_code=bad)
        self.assertEqual(self.post('/api/admin/login/', otp_code=good).status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_code_is_rejected(self):
        from datetime import timedelta
        from django.utils import timezone
        from users.models import OTPVerification
        self.post('/api/admin/login/')
        OTPVerification.objects.filter(phone_number=self.admin.phone_number).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.post('/api/admin/login/', otp_code=self.code()).status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_less_code_login_is_closed_for_super_admin(self):
        res = self.client.post('/api/auth/login-otp/', {'phone_number': self.admin.phone_number}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        from datetime import timedelta
        from django.utils import timezone
        from users.models import OTPVerification
        OTPVerification.objects.create(phone_number=self.admin.phone_number, otp_code='654321', expires_at=timezone.now() + timedelta(minutes=5))
        res = self.client.post('/api/auth/verify-otp/', {'phone_number': self.admin.phone_number, 'otp_code': '654321'}, format='json')
        self.assertNotIn('access_token', str(res.data))
        self.assertNotIn('access_token', res.cookies)


class DefaultRolesTestCase(TestCase):
    """Default roles exist after migrate and limit staff to their own area."""

    def staff_with(self, role, phone):
        from django.contrib.auth.models import Group
        user = User.objects.create_user(phone_number=phone, password='password123', is_staff=True, is_approved=True, is_phone_verified=True)
        user.groups.add(Group.objects.get(name=role))
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_default_roles_are_created_with_permissions(self):
        from django.contrib.auth.models import Group
        from users.roles import DEFAULT_ROLES
        for name in DEFAULT_ROLES:
            self.assertTrue(Group.objects.get(name=name).permissions.exists(), name)
        vendor = Group.objects.get(name='retailer')
        self.assertTrue(vendor.permissions.filter(codename='add_product').exists())
        self.assertFalse(vendor.permissions.filter(codename='can_auto_approve_product').exists())
        self.assertFalse(Group.objects.get(name='buyer').permissions.filter(codename='add_product').exists())

    def test_accountant_sees_reports_but_cannot_manage_orders(self):
        client = self.staff_with('Accountant', '01877770001')
        self.assertEqual(client.get('/api/finance/reports/').status_code, 200)
        self.assertEqual(client.get('/api/orders/admin/orders/').status_code, 200)
        self.assertEqual(client.post('/api/orders/admin/orders/1/approve/', {}, format='json').status_code, 403)
        self.assertEqual(client.get('/api/admin/staff/').status_code, 403)

    def test_order_manager_cannot_see_money(self):
        client = self.staff_with('Order manager', '01877770002')
        self.assertEqual(client.get('/api/orders/admin/orders/').status_code, 200)
        self.assertEqual(client.get('/api/finance/reports/').status_code, 403)
        self.assertEqual(client.get('/api/finance/ledger/').status_code, 403)

    def test_setup_roles_keeps_admin_changes_unless_reset(self):
        from django.contrib.auth.models import Group
        from users.roles import setup_default_roles
        role = Group.objects.get(name='Accountant')
        role.permissions.clear()
        setup_default_roles()
        self.assertFalse(role.permissions.exists())
        setup_default_roles(reset=True)
        self.assertTrue(role.permissions.exists())
