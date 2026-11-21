"""
Money reports for the admin, worked out from orders plus the ledger of money that actually moved.

How an order's money splits (amounts in BDT):
    customer pays   = product sales + delivery charge - coupon discount
    commission      = platform's cut of the product sales (OrderCommission)
    vendor earning  = product sales - commission            (what the platform owes the shop)
    courier fee     = what the courier charges for the parcel (Pathao fee, else the delivery charge)
    COD fee         = courier's cash-handling fee on cash-on-delivery money
    gateway fee     = payment gateway's clearance fee on online payments
    platform net    = commission + delivery charge - discount - courier fee - COD fee - gateway fee

Sales count once an order is DELIVERED. Balances (owed to vendors, due from the courier and the
gateway, refunds to pay) are always all-time, so they match what is really outstanding.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Prefetch, Sum
from django.utils import timezone

from orders.models import Order, OrderItem
from .models import FinanceSettings, LedgerEntry

ZERO = Decimal('0.00')
CLOSED = ('CANCELLED', 'RETURNED', 'REJECTED')
OPEN = ('PENDING_ADMIN_APPROVAL', 'APPROVED')
MAX_ROWS = 500


def money(value):
    return Decimal(value or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def parse_range(params):
    """`from` / `to` as YYYY-MM-DD (inclusive); defaults to the last 30 days."""
    today = timezone.localdate()

    def parse(value, default):
        try:
            return date.fromisoformat(value) if value else default
        except ValueError:
            return default

    end = parse(params.get('to'), today)
    start = parse(params.get('from'), end - timedelta(days=29))
    if start > end:
        start, end = end, start
    return start, end


def _aware(d, end=False):
    return timezone.make_aware(datetime.combine(d + timedelta(days=1) if end else d, time.min))


class OrderMoney:
    """Money figures for one order (items and their commission records prefetched)."""

    def __init__(self, order, fees):
        self.order = order
        o = order
        self.items = list(o.items.all())
        self.sales = money(o.total_amount)
        self.discount = money(o.discount_amount)
        self.delivery = money(o.total_delivery_charge)
        self.paid_by_customer = money(self.sales + self.delivery - self.discount)
        self.commission = money(sum(
            (getattr(i, 'commission_record', None).commission_amount if getattr(i, 'commission_record', None) else ZERO)
            for i in self.items
        ))
        self.delivered = o.status == 'DELIVERED'
        self.closed = o.status in CLOSED
        # The courier charges for every parcel it carried, delivered or returned
        self.dispatched = bool(o.pathao_consignment_id) or self.delivered
        self.in_transit = self.dispatched and not self.delivered and not self.closed
        fee = money(o.pathao_delivery_fee) or self.delivery
        # Charged once the parcel is delivered or comes back; nothing yet while it is on the way
        self.courier_fee = fee if (self.dispatched and not self.in_transit) else ZERO
        self.cash_collected = self.paid_by_customer if (self.delivered and o.payment_method == 'COD') else ZERO
        self.cod_fee = money(self.cash_collected * fees.courier_cod_fee_percent / 100)
        self.online_paid = self.paid_by_customer if (o.payment_method == 'ONLINE' and o.payment_status == 'PAID') else ZERO
        self.gateway_fee = money(self.online_paid * fees.gateway_fee_percent / 100)
        # Courier pays out the cash it collected minus its charges (charges for prepaid parcels too)
        self.courier_net = money(self.cash_collected - self.courier_fee - self.cod_fee)
        self.refund_due = self.online_paid if self.closed else ZERO

    @property
    def platform_net(self):
        if not self.delivered:
            return money(-self.courier_fee - self.gateway_fee)
        return money(self.commission + self.delivery - self.discount - self.courier_fee - self.cod_fee - self.gateway_fee)

    def row(self):
        o = self.order
        return {
            'id': o.id,
            'order_number': o.order_number,
            'date': timezone.localtime(o.created_at).date().isoformat(),
            'status': o.status,
            'courier_status': o.pathao_order_status,
            'payment_method': o.payment_method,
            'payment_status': o.payment_status,
            'buyer': (o.buyer.full_name or o.buyer.phone_number) if o.buyer_id else '',
            'sales': self.sales,
            'discount': self.discount,
            'delivery': self.delivery,
            'paid_by_customer': self.paid_by_customer,
            'commission': self.commission,
            'courier_fee': self.courier_fee,
            'cod_fee': self.cod_fee,
            'gateway_fee': self.gateway_fee,
            'cash_collected': self.cash_collected,
            'courier_net': self.courier_net,
            'online_paid': self.online_paid,
            'platform_net': self.platform_net,
            'is_restocked': o.is_restocked,
        }


def _orders(qs=None):
    qs = qs if qs is not None else Order.objects.all()
    items = OrderItem.objects.select_related('product__category__parent__parent', 'shop', 'commission_record')
    return qs.select_related('buyer').prefetch_related(Prefetch('items', queryset=items), 'vendor_orders').order_by('-created_at')


def _sum(rows, attr):
    return money(sum((getattr(r, attr) for r in rows), ZERO))


def _ledger_totals(qs):
    return {k: money(v) for k, v in qs.values_list('kind').annotate(total=Sum('amount')).values_list('kind', 'total')}


def _root_category(product):
    cat = product.category if product else None
    while cat is not None and cat.parent_id:
        cat = cat.parent
    return cat


def build_report(params):
    fees = FinanceSettings.load()
    start, end = parse_range(params)
    all_orders = [OrderMoney(o, fees) for o in _orders()]
    in_range = [m for m in all_orders if start <= timezone.localtime(m.order.created_at).date() <= end]
    delivered = [m for m in in_range if m.delivered]

    ledger_all = LedgerEntry.objects.all()
    ledger_range = ledger_all.filter(date__gte=start, date__lte=end)
    totals_all = _ledger_totals(ledger_all)
    totals_range = _ledger_totals(ledger_range)

    # ---------- Overview ----------
    status_counts = defaultdict(int)
    for m in in_range:
        status_counts[m.order.status] += 1
    other_income = totals_range.get(LedgerEntry.OTHER_INCOME, ZERO)
    expenses = totals_range.get(LedgerEntry.EXPENSE, ZERO)
    courier_fees = _sum([m for m in in_range if m.dispatched], 'courier_fee')
    overview = {
        'orders': len(in_range),
        'delivered_orders': len(delivered),
        'status_counts': dict(status_counts),
        'gross_sales': _sum(delivered, 'sales'),
        'discounts': _sum(delivered, 'discount'),
        'delivery_charges': _sum(delivered, 'delivery'),
        'customer_paid': _sum(delivered, 'paid_by_customer'),
        'commission': _sum(delivered, 'commission'),
        'vendor_earnings': money(_sum(delivered, 'sales') - _sum(delivered, 'commission')),
        'courier_fees': courier_fees,
        'cod_fees': _sum(in_range, 'cod_fee'),
        'gateway_fees': _sum(in_range, 'gateway_fee'),
        'refunds_paid': totals_range.get(LedgerEntry.REFUND, ZERO),
        'vendor_payouts': totals_range.get(LedgerEntry.VENDOR_PAYOUT, ZERO),
        'courier_received': totals_range.get(LedgerEntry.COURIER_REMITTANCE, ZERO),
        'gateway_received': totals_range.get(LedgerEntry.GATEWAY_SETTLEMENT, ZERO),
        'other_income': other_income,
        'expenses': expenses,
        'pipeline_value': _sum([m for m in in_range if m.order.status in OPEN], 'paid_by_customer'),
        'pipeline_orders': sum(1 for m in in_range if m.order.status in OPEN),
        'returned_orders': sum(1 for m in in_range if m.closed),
    }
    overview['platform_net'] = money(
        overview['commission'] + overview['delivery_charges'] - overview['discounts']
        - overview['courier_fees'] - overview['cod_fees'] - overview['gateway_fees'] + other_income - expenses
    )
    overview['average_order'] = money(overview['customer_paid'] / len(delivered)) if delivered else ZERO

    # ---------- Sales ----------
    daily = {}
    d = start
    while d <= end:
        daily[d] = {'date': d.isoformat(), 'orders': 0, 'delivered': 0, 'sales': ZERO, 'commission': ZERO}
        d += timedelta(days=1)
    by_method = defaultdict(lambda: {'orders': 0, 'amount': ZERO})
    by_source = defaultdict(lambda: {'orders': 0, 'amount': ZERO})
    by_product = {}
    by_category = {}
    by_vendor_range = {}
    for m in in_range:
        day = daily.get(timezone.localtime(m.order.created_at).date())
        if day:
            day['orders'] += 1
        if not m.delivered:
            continue
        if day:
            day['delivered'] += 1
            day['sales'] += m.sales
            day['commission'] += m.commission
        by_method[m.order.payment_method]['orders'] += 1
        by_method[m.order.payment_method]['amount'] += m.paid_by_customer
        by_source[m.order.source]['orders'] += 1
        by_source[m.order.source]['amount'] += m.paid_by_customer
        for i in m.items:
            line = money(i.quantity * i.unit_price)
            comm = i.commission_record.commission_amount if getattr(i, 'commission_record', None) else ZERO
            key = i.product_id or f'x{i.id}'
            p = by_product.setdefault(key, {
                'product_id': i.product_id, 'title': i.product.title if i.product else 'Deleted product',
                'shop': i.shop.shop_name if i.shop_id else '', 'quantity': 0, 'sales': ZERO,
            })
            p['quantity'] += i.quantity
            p['sales'] += line
            root = _root_category(i.product)
            c = by_category.setdefault(root.id if root else 0, {'category': root.name if root else 'Uncategorised', 'quantity': 0, 'sales': ZERO})
            c['quantity'] += i.quantity
            c['sales'] += line
            if i.shop_id:
                v = by_vendor_range.setdefault(i.shop_id, {'shop_id': i.shop_id, 'shop': i.shop.shop_name, 'orders': set(), 'quantity': 0, 'sales': ZERO, 'commission': ZERO})
                v['orders'].add(m.order.id)
                v['quantity'] += i.quantity
                v['sales'] += line
                v['commission'] += comm
    vendors_range = []
    for v in by_vendor_range.values():
        v['orders'] = len(v['orders'])
        v['earning'] = money(v['sales'] - v['commission'])
        vendors_range.append(v)
    sales = {
        'daily': list(daily.values()),
        'by_payment_method': [{'method': k, **v} for k, v in by_method.items()],
        'by_source': [{'source': k, **v} for k, v in by_source.items()],
        'top_products': sorted(by_product.values(), key=lambda p: p['sales'], reverse=True)[:50],
        'by_category': sorted(by_category.values(), key=lambda c: c['sales'], reverse=True),
        'by_vendor': sorted(vendors_range, key=lambda v: v['sales'], reverse=True),
    }

    # ---------- Vendor settlement (all-time balances) ----------
    from vendors.models import ShopProfile
    payouts = defaultdict(lambda: ZERO)
    last_payout = {}
    for e in ledger_all.filter(kind=LedgerEntry.VENDOR_PAYOUT, shop__isnull=False).order_by('date'):
        payouts[e.shop_id] += e.amount
        last_payout[e.shop_id] = e.date.isoformat()
    shop_rows = {}
    for m in all_orders:
        if not (m.delivered or m.order.status in OPEN):
            continue
        for i in m.items:
            if not i.shop_id:
                continue
            r = shop_rows.setdefault(i.shop_id, {'sales': ZERO, 'commission': ZERO, 'pending_sales': ZERO, 'orders': set()})
            line = money(i.quantity * i.unit_price)
            if m.delivered:
                r['sales'] += line
                r['commission'] += i.commission_record.commission_amount if getattr(i, 'commission_record', None) else ZERO
                r['orders'].add(m.order.id)
            else:
                r['pending_sales'] += line
    vendors = []
    for shop in ShopProfile.objects.select_related('user').filter(id__in=set(shop_rows) | set(payouts)):
        r = shop_rows.get(shop.id, {'sales': ZERO, 'commission': ZERO, 'pending_sales': ZERO, 'orders': set()})
        earning = money(r['sales'] - r['commission'])
        paid = money(payouts.get(shop.id, ZERO))
        vendors.append({
            'shop_id': shop.id, 'shop': shop.shop_name, 'phone': shop.user.phone_number if shop.user_id else '',
            'delivered_orders': len(r['orders']), 'sales': money(r['sales']), 'commission': money(r['commission']),
            'earning': earning, 'paid': paid, 'due': money(earning - paid),
            'pending_sales': money(r['pending_sales']), 'last_payout': last_payout.get(shop.id),
        })
    vendors.sort(key=lambda v: v['due'], reverse=True)
    vendor_totals = {k: money(sum((v[k] for v in vendors), ZERO)) for k in ('sales', 'commission', 'earning', 'paid', 'due', 'pending_sales')}

    # ---------- Courier ----------
    carried = [m for m in all_orders if m.dispatched]
    courier_expected = _sum(carried, 'courier_net')
    courier_received = totals_all.get(LedgerEntry.COURIER_REMITTANCE, ZERO)
    courier = {
        'totals': {
            'parcels': len(carried),
            'delivered': sum(1 for m in carried if m.delivered),
            'returned': sum(1 for m in carried if m.closed),
            'in_transit': sum(1 for m in carried if m.in_transit),
            'cash_collected': _sum(carried, 'cash_collected'),
            'courier_fees': _sum(carried, 'courier_fee'),
            'cod_fees': _sum(carried, 'cod_fee'),
            'expected': courier_expected,
            'received': courier_received,
            'outstanding': money(courier_expected - courier_received),
        },
        'orders': [m.row() for m in carried if start <= timezone.localtime(m.order.created_at).date() <= end][:MAX_ROWS],
    }

    # ---------- Payment gateway ----------
    online = [m for m in all_orders if m.online_paid]
    gateway_expected = money(_sum(online, 'online_paid') - _sum(online, 'gateway_fee'))
    gateway_received = totals_all.get(LedgerEntry.GATEWAY_SETTLEMENT, ZERO)
    gateway = {
        'totals': {
            'payments': len(online),
            'amount': _sum(online, 'online_paid'),
            'fees': _sum(online, 'gateway_fee'),
            'expected': gateway_expected,
            'received': gateway_received,
            'outstanding': money(gateway_expected - gateway_received),
        },
        'orders': [m.row() for m in online if start <= timezone.localtime(m.order.created_at).date() <= end][:MAX_ROWS],
    }

    # ---------- Refunds & returns ----------
    refunded = defaultdict(lambda: ZERO)
    for order_id, amount in ledger_all.filter(kind=LedgerEntry.REFUND, order__isnull=False).values_list('order_id', 'amount'):
        refunded[order_id] += amount
    closed_all = [m for m in all_orders if m.closed]
    refund_rows = []
    for m in closed_all:
        row = m.row()
        row['refund_due'] = m.refund_due
        row['refunded'] = money(refunded.get(m.order.id, ZERO))
        row['refund_outstanding'] = money(max(m.refund_due - row['refunded'], ZERO))
        row['rejection_reason'] = m.order.rejection_reason
        refund_rows.append(row)
    refunds = {
        'totals': {
            'returned': sum(1 for m in closed_all if m.order.status == 'RETURNED'),
            'cancelled': sum(1 for m in closed_all if m.order.status == 'CANCELLED'),
            'rejected': sum(1 for m in closed_all if m.order.status == 'REJECTED'),
            'value': _sum(closed_all, 'paid_by_customer'),
            'return_courier_fees': _sum([m for m in closed_all if m.dispatched], 'courier_fee'),
            'refund_due': _sum(closed_all, 'refund_due'),
            'refunded': money(sum(refunded.values(), ZERO)),
            'refund_outstanding': money(sum((r['refund_outstanding'] for r in refund_rows), ZERO)),
            'awaiting_restock': sum(1 for m in closed_all if not m.order.is_restocked and len(m.order.vendor_orders.all()) > 0),
        },
        'orders': [r for r in refund_rows if r['refund_outstanding'] > 0 or start <= date.fromisoformat(r['date']) <= end][:MAX_ROWS],
    }

    return {
        'range': {'from': start.isoformat(), 'to': end.isoformat()},
        'fees': {'gateway_fee_percent': fees.gateway_fee_percent, 'courier_cod_fee_percent': fees.courier_cod_fee_percent},
        'overview': overview,
        'sales': sales,
        'vendors': {'totals': vendor_totals, 'rows': vendors},
        'courier': courier,
        'gateway': gateway,
        'refunds': refunds,
    }
