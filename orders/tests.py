from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from lookup.models import Lookup
from vendors.models import City, ShopProfile
from products.models import Product, Category
from orders.models import Cart, CartItem, Order, OrderItem, VendorOrder, DeliveryCharge, OrderCommission
from wallets.models import Wallet, WalletTransaction
from users.services import login_user

User = get_user_model()

class HybridFulfillmentAndPathaoTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Roles
        self.buyer_role, _ = Lookup.objects.get_or_create(name='ROLE', value='BUYER', defaults={'is_active': True})
        self.vendor_role, _ = Lookup.objects.get_or_create(name='ROLE', value='VENDOR', defaults={'is_active': True})
        self.admin_role, _ = Lookup.objects.get_or_create(name='ROLE', value='ADMIN', defaults={'is_active': True})

        # Cities
        self.dhaka, _ = City.objects.get_or_create(name="Dhaka")
        self.chattogram, _ = City.objects.get_or_create(name="Chattogram")

        # Delivery Charges & Central Hub
        self.delivery_charge = DeliveryCharge.objects.create(
            inside_city=Decimal('60.00'),
            outside_city=Decimal('120.00'),
            hub_name="Central ACCS Warehouse",
            hub_address="Tejgaon Industrial Area, Dhaka",
            hub_phone="01999999999",
            hub_city=self.dhaka,
            pathao_hub_store_id="HUB-STORE-001"
        )

        # Users
        self.buyer = User.objects.create_user(phone_number='01811111111', password='password123', full_name='Buyer John', role=self.buyer_role, is_phone_verified=True, is_approved=True)
        self.vendor1_user = User.objects.create_user(phone_number='01822222222', password='password123', full_name='Vendor One', role=self.vendor_role, is_phone_verified=True, is_approved=True)
        self.vendor2_user = User.objects.create_user(phone_number='01833333333', password='password123', full_name='Vendor Two', role=self.vendor_role, is_phone_verified=True, is_approved=True)
        self.admin = User.objects.create_superuser(phone_number='01844444444', password='password123', full_name='Admin Boss', role=self.admin_role)

        # Shop Profiles
        self.shop1 = ShopProfile.objects.create(
            user=self.vendor1_user,
            shop_name="Shop Alpha",
            shop_address="Dhanmondi 27, Dhaka",
            city=self.dhaka,
            pathao_store_id="SHOP1-PTH-001"
        )
        self.shop2 = ShopProfile.objects.create(
            user=self.vendor2_user,
            shop_name="Shop Beta",
            shop_address="Agrabad, Chattogram",
            city=self.chattogram,
            pathao_store_id="SHOP2-PTH-002"
        )

        # Category & Products
        self.cat = Category.objects.create(name="Electronics")
        self.prod1 = Product.objects.create(
            shop=self.shop1,
            category=self.cat,
            title="Wireless Mouse",
            price=Decimal('500.00'),
            stock_quantity=50,
            moq=1,
            woner_commission=Decimal('10.00'), # 10%
            approval_status='APPROVED',
            is_active=True
        )
        self.prod2 = Product.objects.create(
            shop=self.shop2,
            category=self.cat,
            title="Mechanical Keyboard",
            price=Decimal('1500.00'),
            stock_quantity=30,
            moq=1,
            woner_commission=Decimal('5.00'), # 5%
            approval_status='APPROVED',
            is_active=True
        )

        # Generate Tokens
        self.buyer_token, _ = login_user(self.buyer)
        self.admin_token, _ = login_user(self.admin)

    def test_single_vendor_checkout_direct_pickup(self):
        """Single-vendor cart checkout defaults to DIRECT_VENDOR fulfillment with shop address & store ID."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.buyer_token}')
        
        # Add item to cart
        cart_resp = self.client.post('/api/orders/cart/add/', {'product_id': self.prod1.id, 'quantity': 2}, format='json')
        self.assertEqual(cart_resp.status_code, status.HTTP_200_OK)

        # Place Order (Checkout)
        checkout_payload = {
            'shipping_address': 'Mirpur 10, Dhaka',
            'contact_phone': '01811111111',
            'buyer_city': self.dhaka.id,
            'payment_method': 'COD'
        }
        order_resp = self.client.post('/api/orders/buyer/orders/', checkout_payload, format='json')
        self.assertEqual(order_resp.status_code, status.HTTP_201_CREATED)
        
        order_data = order_resp.data
        self.assertEqual(order_data['fulfillment_type'], 'DIRECT_VENDOR')
        self.assertEqual(order_data['pickup_address'], self.shop1.shop_address)
        self.assertEqual(order_data['pathao_store_id'], 'SHOP1-PTH-001')
        self.assertEqual(Decimal(str(order_data['total_amount'])), Decimal('1000.00')) # 2 * 500
        self.assertEqual(Decimal(str(order_data['total_delivery_charge'])), Decimal('60.00')) # Inside Dhaka

        # Ensure cart is emptied
        cart = Cart.objects.get(user=self.buyer)
        self.assertEqual(cart.items.count(), 0)

    def test_multi_vendor_checkout_central_hub(self):
        """Multi-vendor cart checkout defaults to CENTRAL_HUB fulfillment with central warehouse address & hub store ID."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.buyer_token}')
        
        # Add items from Shop 1 and Shop 2
        self.client.post('/api/orders/cart/add/', {'product_id': self.prod1.id, 'quantity': 1}, format='json')
        self.client.post('/api/orders/cart/add/', {'product_id': self.prod2.id, 'quantity': 1}, format='json')

        checkout_payload = {
            'shipping_address': 'GEC Circle, Chattogram',
            'contact_phone': '01811111111',
            'buyer_city': self.chattogram.id,
            'payment_method': 'COD'
        }
        order_resp = self.client.post('/api/orders/buyer/orders/', checkout_payload, format='json')
        self.assertEqual(order_resp.status_code, status.HTTP_201_CREATED)

        order_data = order_resp.data
        self.assertEqual(order_data['fulfillment_type'], 'CENTRAL_HUB')
        self.assertEqual(order_data['pickup_address'], self.delivery_charge.hub_address)
        self.assertEqual(order_data['pathao_store_id'], 'HUB-STORE-001')
        # Central Hub -> Chattogram via Pathao live rate (outside Dhaka = 120)
        self.assertEqual(Decimal(str(order_data['total_delivery_charge'])), Decimal('120.00'))

    def test_admin_approve_order_with_overrides_and_commission(self):
        """Admin approval can override pickup & delivery address, recalculates delivery charge, splits VendorOrders, deducts stock, debits commission."""
        # Create order directly
        order = Order.objects.create(
            buyer=self.buyer,
            buyer_city=self.dhaka,
            shipping_address="Dhanmondi, Dhaka",
            contact_phone="01811111111",
            pathao_recipient_city_id=1,
            pathao_recipient_zone_id=101,
            total_amount=Decimal('500.00'),
            total_delivery_charge=Decimal('60.00'),
            fulfillment_type='DIRECT_VENDOR',
            status='PENDING_ADMIN_APPROVAL'
        )
        OrderItem.objects.create(
            order=order,
            product=self.prod1,
            shop=self.shop1,
            quantity=2,
            unit_price=Decimal('500.00')
        )

        initial_stock = self.prod1.stock_quantity
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')

        # Admin overrides pickup address AND delivery address/destination to outside Dhaka
        approve_payload = {
            'pickup_address': 'Custom Pickup Warehouse 4B, Dhaka',
            'pickup_phone': '01777777777',
            'pathao_store_id': 'CUSTOM-STORE-999',
            'shipping_address': 'New Customer Location, Sylhet',
            'contact_phone': '01988888888',
            'pathao_recipient_city_id': 2, # Outside Dhaka
            'pathao_recipient_zone_id': 201,
            'recalculate_delivery_charge': True
        }
        resp = self.client.post(f'/api/orders/admin/orders/{order.id}/approve/', approve_payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        order.refresh_from_db()
        self.assertEqual(order.status, 'APPROVED')
        self.assertEqual(order.pickup_address, 'Custom Pickup Warehouse 4B, Dhaka')
        self.assertEqual(order.pathao_store_id, 'CUSTOM-STORE-999')
        self.assertEqual(order.shipping_address, 'New Customer Location, Sylhet')
        self.assertEqual(order.contact_phone, '01988888888')
        self.assertEqual(order.pathao_recipient_city_id, 2)
        # Recalculated to 120.00 because destination was changed to city 2 (outside Dhaka)
        self.assertEqual(order.total_delivery_charge, Decimal('120.00'))

        # Check stock deduction
        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.stock_quantity, initial_stock - 2)

        # Check VendorOrder creation
        self.assertEqual(order.vendor_orders.count(), 1)
        vorder = order.vendor_orders.first()
        self.assertEqual(vorder.subtotal_amount, Decimal('1000.00'))

        # Check Wallet commission debit (10% of 1000 = 100)
        vendor_wallet = Wallet.objects.get(user=self.vendor1_user)
        self.assertEqual(vendor_wallet.balance, Decimal('-100.00'))
        self.assertEqual(vendor_wallet.transactions.count(), 1)
        self.assertEqual(vendor_wallet.transactions.first().transaction_type, 'OUT')

    def test_pathao_endpoints_and_dispatch(self):
        """Verify Pathao locations, price calculation, dispatch, tracking and webhook."""
        # 1. Cities
        resp = self.client.get('/api/orders/pathao/cities/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 2. Zones
        resp = self.client.get('/api/orders/pathao/zones/?city_id=1')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 3. Calculate Price
        calc_resp = self.client.post('/api/orders/pathao/calculate-price/', {
            'recipient_city': 1,
            'recipient_zone': 101,
            'weight': 1.5
        }, format='json')
        self.assertEqual(calc_resp.status_code, status.HTTP_200_OK)
        self.assertIn('data', calc_resp.data)

        # 4. Dispatch Order
        order = Order.objects.create(
            buyer=self.buyer,
            buyer_city=self.dhaka,
            shipping_address="Banani, Dhaka",
            contact_phone="01811111111",
            total_amount=Decimal('500.00'),
            status='APPROVED'
        )
        OrderItem.objects.create(order=order, product=self.prod1, shop=self.shop1, quantity=1, unit_price=Decimal('500.00'))

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        dispatch_resp = self.client.post(f'/api/orders/admin/orders/{order.id}/dispatch-pathao/', {
            'item_weight': 0.8,
            'special_instruction': 'Handle with care'
        }, format='json')
        self.assertEqual(dispatch_resp.status_code, status.HTTP_200_OK)
        
        order.refresh_from_db()
        self.assertTrue(bool(order.pathao_consignment_id))
        self.assertTrue(bool(order.pathao_tracking_code))

        # 5. Live Tracking
        track_resp = self.client.get(f'/api/orders/admin/orders/{order.id}/track-pathao/')
        self.assertEqual(track_resp.status_code, status.HTTP_200_OK)

        # 6. Webhook Status Event
        self.client.credentials() # Unauthenticated public webhook
        webhook_payload = {
            'consignment_id': order.pathao_consignment_id,
            'order_status': 'Delivered'
        }
        wh_resp = self.client.post('/api/orders/webhooks/pathao/', webhook_payload, format='json')
        self.assertEqual(wh_resp.status_code, status.HTTP_200_OK)

        order.refresh_from_db()
        self.assertEqual(order.pathao_order_status, 'Delivered')
        self.assertEqual(order.payment_status, 'PAID')

    def test_low_stock_endpoint(self):
        """Verify products low-stock endpoint and is_low_stock property."""
        # prod1 has stock_quantity=50, low_stock_threshold=5 -> not low stock
        self.assertFalse(self.prod1.is_low_stock)

        # Update prod1 stock to 3 (below default threshold 5)
        self.prod1.stock_quantity = 3
        self.prod1.save()
        self.assertTrue(self.prod1.is_low_stock)

        # Call low-stock endpoint as admin
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        resp = self.client.get('/api/products/products/low-stock')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        if isinstance(resp.data, list):
            results = resp.data
        elif isinstance(resp.data, dict) and 'data' in resp.data:
            results = resp.data['data']
        else:
            results = resp.data.get('results', [])
        product_ids = [p['id'] for p in results]
        self.assertIn(self.prod1.id, product_ids)
        self.assertNotIn(self.prod2.id, product_ids)

    def test_admin_restock_and_commission_refund(self):
        """Verify Admin restock restores product stock, refunds commission to vendor wallet, and prevents duplicate restock."""
        initial_stock = self.prod1.stock_quantity
        
        # Create and approve an order
        order = Order.objects.create(
            buyer=self.buyer,
            buyer_city=self.dhaka,
            shipping_address="Dhanmondi, Dhaka",
            contact_phone="01811111111",
            total_amount=Decimal('1000.00'),
            total_delivery_charge=Decimal('60.00'),
            status='PENDING_ADMIN_APPROVAL'
        )
        OrderItem.objects.create(order=order, product=self.prod1, shop=self.shop1, quantity=2, unit_price=Decimal('500.00'))

        # Approve order -> stock deducted, commission debited from vendor wallet
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        appr_resp = self.client.post(f'/api/orders/admin/orders/{order.id}/approve/', {}, format='json')
        self.assertEqual(appr_resp.status_code, status.HTTP_200_OK)

        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.stock_quantity, initial_stock - 2)

        vendor_wallet = Wallet.objects.get(user=self.vendor1_user)
        self.assertEqual(vendor_wallet.balance, Decimal('-100.00')) # 10% of 1000 = 100

        # Cannot restock order while it is in APPROVED status unless returned by courier
        bad_restock = self.client.post(f'/api/orders/admin/orders/{order.id}/restock/')
        self.assertEqual(bad_restock.status_code, status.HTTP_400_BAD_REQUEST)

        # Mark order as RETURNED
        order.status = 'RETURNED'
        order.save()

        # Restock order
        restock_resp = self.client.post(f'/api/orders/admin/orders/{order.id}/restock/')
        self.assertEqual(restock_resp.status_code, status.HTTP_200_OK)

        # Stock should be restored
        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.stock_quantity, initial_stock)

        # Vendor wallet should have received refund
        vendor_wallet.refresh_from_db()
        self.assertEqual(vendor_wallet.balance, Decimal('0.00'))
        self.assertEqual(vendor_wallet.transactions.filter(transaction_type='IN').count(), 1)

        # Order and vendor order should be marked restocked
        order.refresh_from_db()
        self.assertTrue(order.is_restocked)
        self.assertIsNotNone(order.restocked_at)
        vorder = order.vendor_orders.first()
        self.assertTrue(vorder.is_restocked)

        # Duplicate restock attempt must fail
        dup_restock = self.client.post(f'/api/orders/admin/orders/{order.id}/restock/')
        self.assertEqual(dup_restock.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already been restocked", dup_restock.data['error'])

    def test_courier_summary_and_dashboard_integration(self):
        """Verify courier-summary endpoint and core admin dashboard analytics."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')

        # Call courier-summary
        resp = self.client.get('/api/orders/admin/orders/courier-summary/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('in_transit_parcels', resp.data)
        self.assertIn('delivered_parcels', resp.data)
        self.assertIn('returned_parcels', resp.data)
        self.assertIn('cancelled_parcels', resp.data)
        self.assertIn('pending_restock_parcels', resp.data)
        self.assertIn('restocked_parcels', resp.data)

        # Call admin dashboard
        dash_resp = self.client.get('/api/admin/dashboard/analytics/')
        self.assertEqual(dash_resp.status_code, status.HTTP_200_OK)
        self.assertIn('inventory_summary', dash_resp.data)
        self.assertIn('courier_summary', dash_resp.data)
        self.assertIn('low_stock_products', dash_resp.data['inventory_summary'])
        self.assertIn('in_transit_parcels', dash_resp.data['courier_summary'])
