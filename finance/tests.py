from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from finance.models import FinanceSettings, LedgerEntry
from orders.models import Order, OrderItem
from products.models import Category, Product
from vendors.models import ShopProfile

User = get_user_model()
D = Decimal


class FinanceReportTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(phone_number='01700001111', password='pw')
        self.buyer = User.objects.create_user(phone_number='01700002222', password='pw', full_name='Rahim')
        vendor = User.objects.create_user(phone_number='01700003333', password='pw')
        self.shop = ShopProfile.objects.create(user=vendor, shop_name='Alpha', shop_address='Dhaka')
        root = Category.objects.create(name='Class 9')
        sub = Category.objects.create(name='Physics', parent=root)
        self.book = Product.objects.create(shop=self.shop, category=sub, title='Physics 9', price=D('500'),
                                           stock_quantity=50, approval_status='APPROVED', woner_commission=D('10'))
        FinanceSettings.objects.create(pk=1, gateway_fee_percent=D('2'), courier_cod_fee_percent=D('1'))
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def order(self, qty=2, method='COD', status='DELIVERED', paid=None, delivery=D('60'), discount=D('0'), fee=D('0'), consignment=True):
        o = Order.objects.create(buyer=self.buyer, shipping_address='x', contact_phone='017', total_amount=D('500') * qty,
                                 total_delivery_charge=delivery, discount_amount=discount, payment_method=method,
                                 pathao_delivery_fee=fee, pathao_consignment_id='C1' if consignment else None)
        OrderItem.objects.create(order=o, product=self.book, shop=self.shop, quantity=qty, unit_price=D('500'))
        o.status = 'APPROVED'
        o.save()  # creates commission records
        o.status = status
        o.payment_status = paid or ('PAID' if status == 'DELIVERED' else 'UNPAID')
        o.save()
        return o

    def report(self):
        res = self.client.get('/api/finance/reports/', {'from': '2000-01-01'})
        self.assertEqual(res.status_code, 200, res.data)
        return res.data

    def test_delivered_cod_order_money(self):
        self.order(qty=2, delivery=D('60'), discount=D('50'), fee=D('70'))
        r = self.report()
        ov = r['overview']
        self.assertEqual(ov['gross_sales'], D('1000.00'))
        self.assertEqual(ov['customer_paid'], D('1010.00'))       # 1000 + 60 - 50
        self.assertEqual(ov['commission'], D('100.00'))            # 10%
        self.assertEqual(ov['courier_fees'], D('70.00'))           # Pathao's own fee wins
        self.assertEqual(ov['cod_fees'], D('10.10'))               # 1% of the cash
        self.assertEqual(ov['platform_net'], D('29.90'))           # 100 + 60 - 50 - 70 - 10.10
        c = r['courier']['totals']
        self.assertEqual(c['expected'], D('930.00') - D('0.10'))   # 1010 - 70 - 10.10
        v = r['vendors']['rows'][0]
        self.assertEqual((v['earning'], v['due']), (D('900.00'), D('900.00')))
        self.assertEqual(r['sales']['by_category'][0]['category'], 'Class 9')

    def test_ledger_reduces_balances(self):
        self.order(qty=1)  # 500 + 60, COD
        self.client.post('/api/finance/ledger/', {'kind': 'VENDOR_PAYOUT', 'amount': '300', 'shop': self.shop.id}, format='json')
        self.client.post('/api/finance/ledger/', {'kind': 'COURIER_REMITTANCE', 'amount': '400'}, format='json')
        r = self.report()
        self.assertEqual(r['vendors']['rows'][0]['due'], D('150.00'))          # 450 earning - 300
        expected = D('560') - D('60') - D('5.60')
        self.assertEqual(r['courier']['totals']['outstanding'], expected - D('400'))
        self.assertEqual(r['overview']['vendor_payouts'], D('300.00'))

    def test_online_payment_gateway_fee_and_refund(self):
        o = self.order(qty=1, method='ONLINE', status='RETURNED', paid='PAID')
        r = self.report()
        self.assertEqual(r['gateway']['totals']['fees'], D('11.20'))           # 2% of 560
        self.assertEqual(r['refunds']['totals']['refund_due'], D('560.00'))
        self.assertEqual(r['refunds']['totals']['return_courier_fees'], D('60.00'))
        self.client.post('/api/finance/ledger/', {'kind': 'REFUND', 'amount': '560', 'order': o.id, 'method': 'BKASH'}, format='json')
        r = self.report()
        self.assertEqual(r['refunds']['totals']['refund_outstanding'], D('0.00'))

    def test_in_transit_parcel_has_no_courier_charge_yet(self):
        self.order(status='APPROVED')
        c = self.report()['courier']['totals']
        self.assertEqual((c['in_transit'], c['courier_fees'], c['outstanding']), (1, D('0.00'), D('0.00')))

    def test_ledger_validation_and_access(self):
        res = self.client.post('/api/finance/ledger/', {'kind': 'VENDOR_PAYOUT', 'amount': '100'}, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.post('/api/finance/ledger/', {'kind': 'EXPENSE', 'amount': '-5'}, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.patch('/api/finance/settings/', {'gateway_fee_percent': '1.5'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(FinanceSettings.load().gateway_fee_percent, D('1.5'))
        buyer = APIClient()
        buyer.force_authenticate(self.buyer)
        self.assertEqual(buyer.get('/api/finance/reports/').status_code, 403)
        self.assertEqual(APIClient().get('/api/finance/ledger/').status_code, 401)
