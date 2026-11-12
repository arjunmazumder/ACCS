"""
Order creation shared by the cart checkout and landing-page orders.

    order = place_order(buyer=user, lines=[(product, qty), ...], shipping=..., coupon_code='EID10')

Raises CheckoutError with a buyer-friendly message when something is not orderable.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from orders.models import DeliveryCharge, Order, OrderItem
from orders.services.pathao import PathaoService
from orders.utils import calculate_product_unit_price


class CheckoutError(Exception):
    pass


def resolve_coupon(code, subtotal):
    """Return (coupon, discount). Raises CheckoutError if the code can't be used."""
    if not code:
        return None, Decimal('0.00')
    from marketing.models import Coupon
    coupon = Coupon.objects.filter(code__iexact=code.strip()).first()
    if not coupon:
        raise CheckoutError('This coupon code does not exist.')
    discount, error = coupon.evaluate(subtotal)
    if error:
        raise CheckoutError(error)
    return coupon, discount


def validate_lines(lines):
    """lines: iterable of (product, quantity). Returns [(product, qty, unit_price)]."""
    priced = []
    for product, quantity in lines:
        quantity = int(quantity)
        if quantity <= 0:
            continue
        if not product.is_active or product.approval_status != 'APPROVED' or (product.shop and product.shop.is_blocked):
            raise CheckoutError(f"'{product.title}' is no longer available.")
        if product.stock_quantity < quantity:
            raise CheckoutError(f"'{product.title}' has only {product.stock_quantity} in stock.")
        if product.moq and quantity < product.moq:
            raise CheckoutError(f"Minimum order quantity for '{product.title}' is {product.moq}.")
        priced.append((product, quantity, calculate_product_unit_price(product, quantity)))
    if not priced:
        raise CheckoutError('Select at least one product to order.')
    return priced


def place_order(*, buyer, lines, shipping_address, contact_phone, buyer_city=None,
                recipient_city_id=None, recipient_zone_id=None, recipient_area_id=None,
                payment_method='COD', coupon_code=None, source='WEBSITE', landing_page=None, note=None):
    priced = validate_lines(lines)
    subtotal = sum(qty * price for _, qty, price in priced)
    coupon, discount = resolve_coupon(coupon_code, subtotal)

    recipient_city_id = recipient_city_id or 1
    recipient_zone_id = recipient_zone_id or 101

    # Hybrid fulfilment: one shop → direct pickup, several shops → central hub
    shops = list({p.shop for p, _, _ in priced if p.shop})
    hub = DeliveryCharge.objects.first()
    if len(shops) <= 1:
        fulfillment_type = 'DIRECT_VENDOR'
        shop = shops[0] if shops else None
        pickup_address = shop.shop_address if shop else (hub.hub_address if hub else 'Vendor Shop')
        pickup_phone = shop.user.phone_number if shop and shop.user else contact_phone
        pickup_city = shop.city if shop else None
        store_id = shop.pathao_store_id if shop else None
    else:
        fulfillment_type = 'CENTRAL_HUB'
        pickup_address = hub.hub_address if hub else 'Central Warehouse'
        pickup_phone = hub.hub_phone if hub else '01700000000'
        pickup_city = hub.hub_city if hub else None
        store_id = hub.pathao_hub_store_id if hub else None

    # Live Pathao delivery price with sensible fallbacks
    weight = max(0.5, sum(qty * 0.5 for _, qty, _ in priced))
    pricing = PathaoService().calculate_price(
        store_id=store_id, recipient_city=recipient_city_id, recipient_zone=recipient_zone_id, weight=weight,
    )
    if pricing and 'data' in pricing and 'price' in pricing['data']:
        delivery = Decimal(str(pricing['data']['price']))
    else:
        delivery = Decimal('60.00') if str(recipient_city_id) == '1' else Decimal('120.00')

    with transaction.atomic():
        order = Order.objects.create(
            buyer=buyer, buyer_city=buyer_city,
            shipping_address=shipping_address, contact_phone=contact_phone,
            total_amount=subtotal, total_delivery_charge=delivery,
            discount_amount=discount, coupon=coupon, coupon_code=coupon.code if coupon else None,
            payment_method=payment_method or 'COD', payment_status='UNPAID',
            fulfillment_type=fulfillment_type,
            pickup_address=pickup_address, pickup_phone=pickup_phone, pickup_city=pickup_city,
            pathao_store_id=store_id,
            pathao_recipient_city_id=recipient_city_id,
            pathao_recipient_zone_id=recipient_zone_id,
            pathao_recipient_area_id=recipient_area_id,
            status='PENDING_ADMIN_APPROVAL',
            source=source, landing_page=landing_page, customer_note=note or None,
        )
        for product, qty, price in priced:
            OrderItem.objects.create(order=order, product=product, shop=product.shop, quantity=qty, unit_price=price)
        if coupon:
            type(coupon).objects.filter(pk=coupon.pk).update(times_used=F('times_used') + 1)
    return order
