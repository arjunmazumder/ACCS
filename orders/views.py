from rest_framework import viewsets, permissions, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from users.permissions import IsAdminOrSuperAdmin

from .models import Cart, CartItem, Order, OrderItem, VendorOrder, DeliveryCharge, OrderCommission
from products.models import Product
from .serializers import (
    CartSerializer, CartItemSerializer, OrderSerializer, VendorOrderSerializer,
    DeliveryChargeSerializer, OrderCommissionSerializer,
    AddToCartSerializer, UpdateCartQuantitySerializer, RemoveFromCartSerializer,
    CheckoutSerializer, AdminOrderApproveSerializer,
    PathaoCalculatePriceSerializer, PathaoDispatchSerializer,
    VendorOrderStatusUpdateSerializer, PathaoWebhookEventSerializer
)
from .utils import calculate_product_unit_price
from .services.pathao import PathaoService
from .services.checkout import CheckoutError, place_order

def is_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    if hasattr(user, 'role') and user.role and user.role.name == 'ROLE' and user.role.value == 'ADMIN':
        return True
    return False

import uuid

@extend_schema(tags=['Orders'])
class CartViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = CartSerializer

    def get_cart(self, request):
        user = request.user if request.user and request.user.is_authenticated else None
        guest_id = (
            request.headers.get('x-guest-id') or 
            request.COOKIES.get('guest_id') or 
            request.query_params.get('guest_id') or 
            (request.data.get('guest_id') if isinstance(request.data, dict) else None)
        )

        if user:
            cart, created = Cart.objects.get_or_create(user=user)
            # If a guest_id was provided, merge any guest cart items into the user's cart
            if guest_id:
                guest_cart = Cart.objects.filter(guest_id=guest_id).first()
                if guest_cart and guest_cart != cart:
                    for g_item in guest_cart.items.all():
                        u_item, u_created = CartItem.objects.get_or_create(
                            cart=cart,
                            product=g_item.product,
                            defaults={'quantity': g_item.quantity, 'unit_price': g_item.unit_price}
                        )
                        if not u_created:
                            u_item.quantity += g_item.quantity
                            u_item.unit_price = calculate_product_unit_price(u_item.product, u_item.quantity)
                            u_item.save()
                    guest_cart.delete()
            return cart

        if guest_id:
            cart, created = Cart.objects.get_or_create(guest_id=guest_id, defaults={'user': None})
            return cart

        # Generate a new unique guest_id for unauthenticated visitor
        new_guest_id = str(uuid.uuid4())
        cart = Cart.objects.create(guest_id=new_guest_id, user=None)
        return cart

    @extend_schema(summary="Get current user or guest cart", responses={200: CartSerializer})
    def list(self, request):
        cart = self.get_cart(request)
        serializer = CartSerializer(cart)
        response = Response(serializer.data)
        if cart.guest_id:
            response.set_cookie('guest_id', cart.guest_id, max_age=30*24*60*60, httponly=False, samesite='Lax')
        return response

    @extend_schema(
        summary="Add product to cart (Supports Guest & Authenticated)",
        request=AddToCartSerializer,
        responses={200: CartSerializer}
    )
    @action(detail=False, methods=['post'])
    def add(self, request):
        cart = self.get_cart(request)
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))

        if not product_id:
            return Response({"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        product = get_object_or_404(Product, id=product_id, is_active=True, approval_status='APPROVED')

        if product.stock_quantity < quantity:
            return Response({"error": f"Only {product.stock_quantity} items in stock"}, status=status.HTTP_400_BAD_REQUEST)
        if product.moq and quantity < product.moq:
            return Response({"error": f"Minimum order quantity is {product.moq}"}, status=status.HTTP_400_BAD_REQUEST)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity, 'unit_price': 0}
        )

        if not created:
            new_quantity = cart_item.quantity + quantity
            if product.stock_quantity < new_quantity:
                return Response({"error": f"Only {product.stock_quantity} items in stock"}, status=status.HTTP_400_BAD_REQUEST)
            cart_item.quantity = new_quantity
            
        cart_item.unit_price = calculate_product_unit_price(product, cart_item.quantity)
        cart_item.save()

        response = Response(CartSerializer(cart).data)
        if cart.guest_id:
            response.set_cookie('guest_id', cart.guest_id, max_age=30*24*60*60, httponly=False, samesite='Lax')
        return response

    @extend_schema(
        summary="Update quantity of product in cart",
        request=UpdateCartQuantitySerializer,
        responses={200: CartSerializer}
    )
    @action(detail=False, methods=['post'])
    def update_quantity(self, request):
        cart = self.get_cart(request)
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 0))

        if not product_id:
            return Response({"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
        except CartItem.DoesNotExist:
            return Response({"error": "Item not found in cart"}, status=status.HTTP_404_NOT_FOUND)

        if quantity <= 0:
            cart_item.delete()
        else:
            product = cart_item.product
            if product.stock_quantity < quantity:
                return Response({"error": f"Only {product.stock_quantity} items in stock"}, status=status.HTTP_400_BAD_REQUEST)
            if product.moq and quantity < product.moq:
                return Response({"error": f"Minimum order quantity is {product.moq}"}, status=status.HTTP_400_BAD_REQUEST)

            cart_item.quantity = quantity
            cart_item.unit_price = calculate_product_unit_price(product, quantity)
            cart_item.save()

        response = Response(CartSerializer(cart).data)
        if cart.guest_id:
            response.set_cookie('guest_id', cart.guest_id, max_age=30*24*60*60, httponly=False, samesite='Lax')
        return response

    @extend_schema(
        summary="Remove product from cart",
        request=RemoveFromCartSerializer,
        responses={200: CartSerializer}
    )
    @action(detail=False, methods=['post'])
    def remove(self, request):
        cart = self.get_cart(request)
        product_id = request.data.get('product_id')

        if not product_id:
            return Response({"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
            cart_item.delete()
        except CartItem.DoesNotExist:
            pass

        response = Response(CartSerializer(cart).data)
        if cart.guest_id:
            response.set_cookie('guest_id', cart.guest_id, max_age=30*24*60*60, httponly=False, samesite='Lax')
        return response

    @extend_schema(summary="Clear entire cart", responses={200: CartSerializer})
    @action(detail=False, methods=['post'])
    def clear(self, request):
        cart = self.get_cart(request)
        cart.items.all().delete()
        response = Response(CartSerializer(cart).data)
        if cart.guest_id:
            response.set_cookie('guest_id', cart.guest_id, max_age=30*24*60*60, httponly=False, samesite='Lax')
        return response

@extend_schema(tags=['Orders'])
class OrderViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'head', 'options']
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'payment_status', 'payment_method', 'fulfillment_type']
    search_fields = ['order_number', 'contact_phone']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Order.objects.none()
        if is_admin(user):
            return Order.objects.all().order_by('-created_at')
        return Order.objects.filter(buyer=user).order_by('-created_at')

    @extend_schema(
        summary="Place Order (Checkout active buyer cart)",
        request=CheckoutSerializer,
        responses={201: OrderSerializer}
    )
    def create(self, request, *args, **kwargs):
        # Validate checkout input
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Fetch user's cart
        cart = Cart.objects.filter(user=request.user).first()
        if not cart or not cart.items.exists():
            return Response({"error": "Your cart is empty. Add products before placing an order."}, status=status.HTTP_400_BAD_REQUEST)
        cart_items = list(cart.items.select_related('product', 'product__shop', 'product__shop__city').all())

        # Shipping details, falling back to the buyer's saved address
        shipping_address = data.get('shipping_address')
        contact_phone = data.get('contact_phone')
        buyer_city = data.get('buyer_city')
        recipient_city_id = data.get('pathao_recipient_city_id')
        recipient_zone_id = data.get('pathao_recipient_zone_id')
        recipient_area_id = data.get('pathao_recipient_area_id')

        saved_addr = getattr(request.user, 'shipping_address', None)
        if not shipping_address:
            if not saved_addr:
                return Response({"error": "Shipping address is required. Please provide shipping_address or save one in your profile."}, status=status.HTTP_400_BAD_REQUEST)
            shipping_address = saved_addr.address
            contact_phone = contact_phone or saved_addr.phone_number
            recipient_city_id = recipient_city_id or saved_addr.pathao_city_id
            recipient_zone_id = recipient_zone_id or saved_addr.pathao_zone_id
            recipient_area_id = recipient_area_id or saved_addr.pathao_area_id
        if not recipient_city_id and buyer_city and 'dhaka' not in buyer_city.name.lower():
            recipient_city_id = buyer_city.id

        try:
            order = place_order(
                buyer=request.user,
                lines=[(item.product, item.quantity) for item in cart_items],
                shipping_address=shipping_address,
                contact_phone=contact_phone or request.user.phone_number,
                buyer_city=buyer_city,
                recipient_city_id=recipient_city_id,
                recipient_zone_id=recipient_zone_id,
                recipient_area_id=recipient_area_id,
                payment_method=data.get('payment_method', 'COD'),
                coupon_code=data.get('coupon_code'),
                note=data.get('note'),
            )
        except CheckoutError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Clear the buyer's cart
        cart.items.all().delete()

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Cancel own order (only while pending admin approval)", request=None, responses={200: OrderSerializer})
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.buyer != request.user and not is_admin(request.user):
            return Response({"error": "You can only cancel your own orders."}, status=status.HTTP_403_FORBIDDEN)
        if order.status != 'PENDING_ADMIN_APPROVAL':
            return Response({"error": "Only orders pending approval can be cancelled. Please contact support."}, status=status.HTTP_400_BAD_REQUEST)
        order.status = 'CANCELLED'
        order.rejection_reason = request.data.get('reason') or 'Cancelled by buyer.'
        order.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        return Response(OrderSerializer(order).data)

    @extend_schema(summary="Track own parcel via Pathao Courier")
    @action(detail=True, methods=['get'], url_path='track')
    def track(self, request, pk=None):
        order = self.get_object()
        if not order.pathao_consignment_id:
            return Response({"error": "This order has not been handed over to the courier yet."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PathaoService().track_consignment(order.pathao_consignment_id))

@extend_schema(tags=['Orders'])
class AdminOrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Order.objects.all().order_by('-created_at')
    serializer_class = OrderSerializer
    permission_classes = [IsAdminOrSuperAdmin]
    action_permission_models = {'commissions': OrderCommission}
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'payment_status', 'payment_method', 'fulfillment_type']
    search_fields = ['order_number', 'buyer__phone_number', 'contact_phone']

    @extend_schema(
        summary="Approve Order (Creates VendorOrders, reserves stock, debits commission, optional pickup & delivery overrides)",
        request=AdminOrderApproveSerializer,
        responses={200: OrderSerializer}
    )
    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        order = self.get_object()
        if order.status != 'PENDING_ADMIN_APPROVAL':
            return Response({"error": f"Cannot approve order with status {order.status}"}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = AdminOrderApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        overrides = serializer.validated_data

        # Pickup Overrides
        if overrides.get('pickup_address'):
            order.pickup_address = overrides['pickup_address']
        if overrides.get('pickup_phone'):
            order.pickup_phone = overrides['pickup_phone']
        if overrides.get('pickup_city'):
            order.pickup_city = overrides['pickup_city']
        if overrides.get('pathao_store_id'):
            order.pathao_store_id = overrides['pathao_store_id']

        # Delivery / Recipient Overrides
        if overrides.get('shipping_address'):
            order.shipping_address = overrides['shipping_address']
        if overrides.get('contact_phone'):
            order.contact_phone = overrides['contact_phone']
        if overrides.get('pathao_recipient_city_id'):
            order.pathao_recipient_city_id = overrides['pathao_recipient_city_id']
        if overrides.get('pathao_recipient_zone_id'):
            order.pathao_recipient_zone_id = overrides['pathao_recipient_zone_id']
        if overrides.get('pathao_recipient_area_id'):
            order.pathao_recipient_area_id = overrides['pathao_recipient_area_id']

        # If delivery destination or pickup store changed, recalculate Pathao delivery fee
        if (overrides.get('pathao_recipient_city_id') or overrides.get('pathao_recipient_zone_id') or overrides.get('pathao_store_id')) and overrides.get('recalculate_delivery_charge', True):
            pathao = PathaoService()
            total_weight = sum(item.quantity * 0.5 for item in order.items.all())
            pricing_resp = pathao.calculate_price(
                store_id=order.pathao_store_id,
                recipient_city=order.pathao_recipient_city_id or 1,
                recipient_zone=order.pathao_recipient_zone_id or 101,
                weight=max(0.5, total_weight)
            )
            if pricing_resp and 'data' in pricing_resp and 'price' in pricing_resp['data']:
                order.total_delivery_charge = Decimal(str(pricing_resp['data']['price']))

        order.status = 'APPROVED'
        order.save()
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        order = self.get_object()
        rejection_reason = request.data.get('rejection_reason', 'Rejected by admin.')
        order.status = 'REJECTED'
        order.rejection_reason = rejection_reason
        order.save()
        return Response(self.get_serializer(order).data)


    @extend_schema(
        summary="Dispatch Order Consignment to Pathao Courier",
        request=PathaoDispatchSerializer,
        responses={200: OpenApiResponse(description="Consignment created in Pathao")}
    )
    @action(detail=True, methods=['post'], url_path='dispatch-pathao')
    def dispatch_pathao(self, request, pk=None):
        order = self.get_object()
        if order.status not in ['APPROVED']:
            return Response({"error": "Only approved orders can be dispatched to Pathao."}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = PathaoDispatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vdata = serializer.validated_data

        pathao = PathaoService()
        result = pathao.create_consignment(
            order=order,
            store_id=vdata.get('store_id'),
            item_quantity=vdata.get('item_quantity', 1),
            item_weight=vdata.get('item_weight', 0.5),
            item_description=vdata.get('item_description'),
            special_instruction=vdata.get('special_instruction')
        )

        if "error" in result:
            return Response({"error": "Pathao dispatch failed", "details": result["error"]}, status=status.HTTP_400_BAD_REQUEST)

        data = result.get('data', {})
        consignment_id = data.get('consignment_id')
        tracking_code = data.get('tracking_code')
        order_status = data.get('order_status', 'Pickup_Pending')
        delivery_fee = data.get('delivery_fee', 0.0)

        if consignment_id:
            order.pathao_consignment_id = consignment_id
        if tracking_code:
            order.pathao_tracking_code = tracking_code
        if order_status:
            order.pathao_order_status = order_status
        if delivery_fee:
            order.pathao_delivery_fee = Decimal(str(delivery_fee))
        order.save(update_fields=['pathao_consignment_id', 'pathao_tracking_code', 'pathao_order_status', 'pathao_delivery_fee', 'updated_at'])

        return Response({
            "message": "Order dispatched to Pathao successfully",
            "pathao_data": data,
            "order": OrderSerializer(order).data
        }, status=status.HTTP_200_OK)

    @extend_schema(summary="Track live parcel timeline via Pathao Courier")
    @action(detail=True, methods=['get'], url_path='track-pathao')
    def track_pathao(self, request, pk=None):
        order = self.get_object()
        if not order.pathao_consignment_id:
            return Response({"error": "This order has not been dispatched to Pathao yet."}, status=status.HTTP_400_BAD_REQUEST)
        
        pathao = PathaoService()
        tracking_info = pathao.track_consignment(order.pathao_consignment_id)
        return Response(tracking_info)

    @extend_schema(summary="1-Click Pathao Delivery Simulator (No typing needed)", request=None)
    @action(detail=True, methods=['post'], url_path='simulate-delivery')
    def simulate_delivery(self, request, pk=None):
        order = self.get_object()
        order.status = 'DELIVERED'
        order.pathao_order_status = 'Delivered'
        order.payment_status = 'PAID'
        order.vendor_orders.filter(status__in=['PENDING', 'PROCESSING', 'PACKED', 'SHIPPED']).update(status='DELIVERED')
        order.save(update_fields=['status', 'pathao_order_status', 'payment_status', 'updated_at'])
        return Response({
            "message": "Order successfully marked as DELIVERED and PAID (Simulated Pathao Webhook)",
            "order": OrderSerializer(order).data
        }, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Restock Cancelled or Returned Order",
        description="Restores inventory stock for all products in this order and refunds debited platform commissions back to vendor wallets. Prevents double restock.",
        responses={200: OrderSerializer}
    )
    @action(detail=True, methods=['post'], url_path='restock')
    def restock(self, request, pk=None):
        order = self.get_object()
        if order.is_restocked:
            return Response({"error": "Order items have already been restocked."}, status=status.HTTP_400_BAD_REQUEST)

        valid_statuses = ['REJECTED', 'CANCELLED', 'RETURNED']
        pathao_returned = (order.pathao_order_status or '').lower() in ['returned', 'cancelled']

        if order.status not in valid_statuses and not pathao_returned:
            return Response({
                "error": f"Order with status '{order.status}' cannot be restocked. Order must be CANCELLED, RETURNED, REJECTED, or marked Returned/Cancelled by courier."
            }, status=status.HTTP_400_BAD_REQUEST)

        from wallets.models import Wallet, WalletTransaction

        with transaction.atomic():
            for vo in order.vendor_orders.filter(is_restocked=False):
                for item in vo.vendor_order_items.all():
                    if item.product:
                        item.product.stock_quantity += item.quantity
                        item.product.save(update_fields=['stock_quantity', 'updated_at'])
                    if hasattr(item, 'commission_record') and item.commission_record.commission_amount > Decimal('0.00'):
                        comm_amt = item.commission_record.commission_amount
                        if item.shop and item.shop.user:
                            wallet, _ = Wallet.objects.get_or_create(user=item.shop.user)
                            wallet.balance += comm_amt
                            wallet.save(update_fields=['balance', 'updated_at'])
                            WalletTransaction.objects.create(
                                wallet=wallet,
                                transaction_type='IN',
                                amount=comm_amt,
                                order_commission=item.commission_record,
                                description=f"Commission refund for restocked Order {order.order_number}"
                            )
                            item.commission_record.commission_amount = Decimal('0.00')
                            item.commission_record.save(update_fields=['commission_amount', 'updated_at'])
                vo.is_restocked = True
                vo.restocked_at = timezone.now()
                if vo.status not in ['CANCELLED', 'RETURNED']:
                    vo.status = 'RETURNED'
                vo.save(update_fields=['is_restocked', 'restocked_at', 'status', 'updated_at'])

            order.is_restocked = True
            order.restocked_at = timezone.now()
            order.restocked_by = request.user
            if order.status not in valid_statuses:
                order.status = 'RETURNED'
            order.save(update_fields=['is_restocked', 'restocked_at', 'restocked_by', 'status', 'updated_at'])

        return Response({
            "message": f"Order {order.order_number} successfully restocked and commissions refunded to vendor wallets.",
            "order": OrderSerializer(order).data
        }, status=status.HTTP_200_OK)

    @extend_schema(summary="List platform commissions earned per order item", responses={200: OrderCommissionSerializer(many=True)})
    @action(detail=False, methods=['get'], url_path='commissions')
    def commissions(self, request):
        queryset = OrderCommission.objects.select_related(
            'order_item__order__buyer', 'order_item__shop__user', 'order_item__product'
        ).order_by('-created_at')
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(order_item__order__order_number__icontains=search) |
                Q(order_item__shop__shop_name__icontains=search) |
                Q(order_item__product__title__icontains=search)
            )
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(OrderCommissionSerializer(page, many=True).data)
        return Response(OrderCommissionSerializer(queryset, many=True).data)

    @extend_schema(
        summary="Courier & Restock Inventory Overview",
        description="Returns counts of active courier consignments, returned/cancelled parcels, and pending restocks.",
        responses={200: OpenApiResponse(description="Courier & restock stats")}
    )
    @action(detail=False, methods=['get'], url_path='courier-summary')
    def courier_summary(self, request):
        in_transit = Order.objects.filter(
            Q(pathao_order_status__in=['Pickup_Pending', 'In_Transit']) |
            (Q(status='APPROVED') & Q(pathao_consignment_id__isnull=False) & ~Q(pathao_order_status__in=['Delivered', 'Returned', 'Cancelled']))
        ).count()
        delivered = Order.objects.filter(Q(status='DELIVERED') | Q(pathao_order_status='Delivered')).count()
        returned = Order.objects.filter(Q(status='RETURNED') | Q(pathao_order_status='Returned')).count()
        cancelled = Order.objects.filter(Q(status__in=['CANCELLED', 'REJECTED']) | Q(pathao_order_status='Cancelled')).count()
        pending_restock = Order.objects.filter(
            Q(status__in=['CANCELLED', 'RETURNED', 'REJECTED']) | Q(pathao_order_status__in=['Returned', 'Cancelled']),
            is_restocked=False,
            vendor_orders__isnull=False
        ).distinct().count()
        restocked = Order.objects.filter(is_restocked=True).count()

        return Response({
            "in_transit_parcels": in_transit,
            "delivered_parcels": delivered,
            "returned_parcels": returned,
            "cancelled_parcels": cancelled,
            "pending_restock_parcels": pending_restock,
            "restocked_parcels": restocked
        })



@extend_schema(tags=['Orders'])
class VendorOrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VendorOrder.objects.all()
    serializer_class = VendorOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status']
    search_fields = ['vendor_order_number', 'parent_order__order_number']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return VendorOrder.objects.none()
        if is_admin(user):
            return VendorOrder.objects.all().order_by('-created_at')
        if hasattr(user, 'vendor_shop_profile'):
            return VendorOrder.objects.filter(vendor_shop=user.vendor_shop_profile).order_by('-created_at')
        return VendorOrder.objects.none()

    @extend_schema(
        summary="Update Vendor Sub-Order Status",
        request=VendorOrderStatusUpdateSerializer,
        responses={200: VendorOrderSerializer}
    )
    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_status(self, request, pk=None):
        vendor_order = self.get_object()
        user = request.user
        if not is_admin(user):
            if not hasattr(user, 'vendor_shop_profile') or vendor_order.vendor_shop != user.vendor_shop_profile:
                return Response({"error": "You do not have permission to update this order."}, status=status.HTTP_403_FORBIDDEN)

        serializer = VendorOrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data['status']

        vendor_order.status = new_status
        vendor_order.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(vendor_order).data)

    @extend_schema(
        summary="Vendor Restock Returned Sub-Order",
        description="Allows vendor (or admin) to restock items from a returned/cancelled sub-order back into shop inventory and receive commission refund.",
        responses={200: VendorOrderSerializer}
    )
    @action(detail=True, methods=['post'], url_path='restock')
    def restock(self, request, pk=None):
        vendor_order = self.get_object()
        user = request.user
        if not is_admin(user):
            if not hasattr(user, 'vendor_shop_profile') or vendor_order.vendor_shop != user.vendor_shop_profile:
                return Response({"error": "You do not have permission to restock this order."}, status=status.HTTP_403_FORBIDDEN)

        if vendor_order.is_restocked:
            return Response({"error": "This vendor order has already been restocked."}, status=status.HTTP_400_BAD_REQUEST)

        valid_statuses = ['CANCELLED', 'RETURNED']
        parent_returned = (vendor_order.parent_order.pathao_order_status or '').lower() in ['returned', 'cancelled']

        if vendor_order.status not in valid_statuses and not parent_returned:
            return Response({
                "error": f"Vendor order with status '{vendor_order.status}' cannot be restocked. Status must be CANCELLED or RETURNED."
            }, status=status.HTTP_400_BAD_REQUEST)

        from wallets.models import Wallet, WalletTransaction

        with transaction.atomic():
            for item in vendor_order.vendor_order_items.all():
                if item.product:
                    item.product.stock_quantity += item.quantity
                    item.product.save(update_fields=['stock_quantity', 'updated_at'])
                if hasattr(item, 'commission_record') and item.commission_record.commission_amount > Decimal('0.00'):
                    comm_amt = item.commission_record.commission_amount
                    if item.shop and item.shop.user:
                        wallet, _ = Wallet.objects.get_or_create(user=item.shop.user)
                        wallet.balance += comm_amt
                        wallet.save(update_fields=['balance', 'updated_at'])
                        WalletTransaction.objects.create(
                            wallet=wallet,
                            transaction_type='IN',
                            amount=comm_amt,
                            order_commission=item.commission_record,
                            description=f"Commission refund for restocked Vendor Order {vendor_order.vendor_order_number}"
                        )
                        item.commission_record.commission_amount = Decimal('0.00')
                        item.commission_record.save(update_fields=['commission_amount', 'updated_at'])

            vendor_order.is_restocked = True
            vendor_order.restocked_at = timezone.now()
            if vendor_order.status not in valid_statuses:
                vendor_order.status = 'RETURNED'
            vendor_order.save(update_fields=['is_restocked', 'restocked_at', 'status', 'updated_at'])

            # If all sibling vendor orders are restocked, mark parent order restocked too
            parent = vendor_order.parent_order
            if not parent.vendor_orders.filter(is_restocked=False).exists():
                parent.is_restocked = True
                parent.restocked_at = timezone.now()
                parent.restocked_by = request.user
                if parent.status not in ['REJECTED', 'CANCELLED', 'RETURNED']:
                    parent.status = 'RETURNED'
                parent.save(update_fields=['is_restocked', 'restocked_at', 'restocked_by', 'status', 'updated_at'])

        return Response({
            "message": f"Vendor Order {vendor_order.vendor_order_number} successfully restocked.",
            "vendor_order": VendorOrderSerializer(vendor_order).data
        }, status=status.HTTP_200_OK)


# --- Pathao Courier Integration Endpoints ---


@extend_schema(tags=['Pathao Courier'])
class PathaoCitiesAPIView(views.APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Get Pathao Deliverable Cities",
        description="Public endpoint to fetch all deliverable cities supported by Pathao Courier.",
        responses={200: OpenApiResponse(description="List of deliverable cities with city_id and city_name")}
    )
    def get(self, request):
        pathao = PathaoService()
        return Response(pathao.get_cities())

@extend_schema(tags=['Pathao Courier'])
class PathaoZonesAPIView(views.APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Get Pathao Zones/Thanas in a City",
        description="Public endpoint to fetch all zones/thanas for a specific city.",
        parameters=[OpenApiParameter(name='city_id', type=int, required=True, description='Pathao City ID (e.g. 1 for Dhaka)')],
        responses={200: OpenApiResponse(description="List of zones for the specified city")}
    )
    def get(self, request):
        city_id = request.query_params.get('city_id', 1)
        pathao = PathaoService()
        return Response(pathao.get_zones(city_id=city_id))

@extend_schema(tags=['Pathao Courier'])
class PathaoAreasAPIView(views.APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Get Pathao Areas in a Zone",
        description="Public endpoint to fetch all areas within a specific zone/thana.",
        parameters=[OpenApiParameter(name='zone_id', type=int, required=True, description='Pathao Zone ID (e.g. 101 for Dhanmondi)')],
        responses={200: OpenApiResponse(description="List of sub-areas within the specified zone")}
    )
    def get(self, request):
        zone_id = request.query_params.get('zone_id', 101)
        pathao = PathaoService()
        return Response(pathao.get_areas(zone_id=zone_id))

@extend_schema(tags=['Pathao Courier'])
class PathaoStoresAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Get Registered Pathao Pickup Stores",
        description="Fetch all registered merchant pickup stores configured in Pathao Aladdin merchant account.",
        responses={200: OpenApiResponse(description="List of pickup stores with store_id and address")}
    )
    def get(self, request):
        pathao = PathaoService()
        return Response(pathao.get_stores())

@extend_schema(tags=['Pathao Courier'])
class PathaoCalculatePriceAPIView(views.APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PathaoCalculatePriceSerializer

    @extend_schema(
        summary="Calculate Live Delivery Price via Pathao",
        description="Calculate estimated delivery charge in BDT based on recipient city/zone and parcel weight.",
        request=PathaoCalculatePriceSerializer,
        responses={200: OpenApiResponse(description="Calculated live delivery fee and plan details")}
    )
    def post(self, request):
        serializer = PathaoCalculatePriceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vdata = serializer.validated_data

        pathao = PathaoService()
        result = pathao.calculate_price(
            store_id=vdata.get('store_id'),
            recipient_city=vdata.get('recipient_city', 1),
            recipient_zone=vdata.get('recipient_zone', 101),
            weight=vdata.get('weight', 0.5),
            item_type=vdata.get('item_type', 1),
            delivery_type=vdata.get('delivery_type', 48)
        )
        return Response(result)

@extend_schema(tags=['Pathao Courier'])
class PathaoWebhookAPIView(views.APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PathaoWebhookEventSerializer

    @extend_schema(
        summary="Pathao Status Webhook Listener",
        description="Webhook endpoint that Pathao calls when parcel delivery status changes.",
        request=PathaoWebhookEventSerializer,
        responses={200: OpenApiResponse(description="Webhook event successfully received and processed")}
    )
    def post(self, request):
        # Validate HMAC signature
        signature = request.headers.get('X-Pathao-Signature') or request.headers.get('x-pathao-signature')
        raw_body = request.body

        pathao = PathaoService()
        if not pathao.verify_webhook_signature(raw_body, signature):
            return Response({"error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        consignment_id = data.get('consignment_id')
        merchant_order_id = data.get('merchant_order_id')
        event_status = data.get('order_status') or data.get('status')

        order = None
        if consignment_id:
            order = Order.objects.filter(pathao_consignment_id=consignment_id).first()
        if not order and merchant_order_id:
            order = Order.objects.filter(order_number=merchant_order_id).first()

        if order and event_status:
            order.pathao_order_status = event_status
            
            # Map Pathao events to ACCS Order & VendorOrder statuses
            normalized_status = str(event_status).lower()
            if 'delivered' in normalized_status:
                order.payment_status = 'PAID'
                order.status = 'DELIVERED'
                order.vendor_orders.filter(status__in=['PENDING', 'PROCESSING', 'PACKED', 'SHIPPED']).update(status='DELIVERED')
            elif 'returned' in normalized_status:
                order.vendor_orders.filter(status__in=['PENDING', 'PROCESSING', 'PACKED', 'SHIPPED']).update(status='CANCELLED')
            elif 'in_transit' in normalized_status or 'picked_up' in normalized_status:
                order.vendor_orders.filter(status__in=['PENDING', 'PROCESSING', 'PACKED']).update(status='SHIPPED')

            order.save(update_fields=['status', 'pathao_order_status', 'payment_status', 'updated_at'])

        return Response({"status": "acknowledged", "consignment_id": consignment_id}, status=status.HTTP_200_OK)



@extend_schema(tags=['Orders'])
class DeliverySettingsAPIView(views.APIView):
    """Central hub & default delivery charge configuration (singleton)."""
    permission_classes = [IsAdminOrSuperAdmin]
    permission_model = DeliveryCharge
    serializer_class = DeliveryChargeSerializer

    def get_object(self):
        obj = DeliveryCharge.objects.first()
        if not obj:
            obj = DeliveryCharge.objects.create(inside_city=60, outside_city=120)
        return obj

    @extend_schema(summary="Get delivery & central hub settings")
    def get(self, request):
        return Response(DeliveryChargeSerializer(self.get_object()).data)

    @extend_schema(summary="Update delivery & central hub settings", request=DeliveryChargeSerializer)
    def patch(self, request):
        serializer = DeliveryChargeSerializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
