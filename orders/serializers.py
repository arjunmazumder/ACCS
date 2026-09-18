from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem, VendorOrder, DeliveryCharge
from products.serializers import ProductSerializer

class DeliveryChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryCharge
        fields = '__all__'

class CartItemSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    subtotal_price = serializers.SerializerMethodField()
    
    class Meta:
        model = CartItem
        fields = ['id', 'cart', 'product', 'product_details', 'quantity', 'unit_price', 'subtotal_price', 'created_at', 'updated_at']
        read_only_fields = ['cart', 'unit_price', 'created_at', 'updated_at']

    def get_subtotal_price(self, obj):
        return obj.quantity * obj.unit_price

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_amount = serializers.SerializerMethodField()
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'user', 'user_name', 'guest_id', 'items', 'total_amount', 'created_at', 'updated_at']
        read_only_fields = ['user', 'guest_id', 'created_at', 'updated_at']

    def get_total_amount(self, obj):
        return sum(item.quantity * item.unit_price for item in obj.items.all())

class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=True, help_text="ID of the product to add to cart")
    quantity = serializers.IntegerField(default=1, min_value=1, help_text="Quantity of product (default: 1)")

class UpdateCartQuantitySerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=True, help_text="ID of the product in cart")
    quantity = serializers.IntegerField(required=True, min_value=0, help_text="New quantity (set to 0 to remove)")

class RemoveFromCartSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=True, help_text="ID of the product to remove from cart")

class OrderItemSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    product_name = serializers.CharField(source='product.title', read_only=True)
    shop_name = serializers.CharField(source='shop.shop_name', read_only=True)
    subtotal_price = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = ['id', 'order', 'product', 'product_name', 'product_details', 'shop', 'shop_name', 'quantity', 'unit_price', 'subtotal_price', 'vendor_order']
        read_only_fields = ['order', 'shop']

    def get_subtotal_price(self, obj):
        return obj.quantity * obj.unit_price

class VendorOrderSerializer(serializers.ModelSerializer):
    vendor_order_items = OrderItemSerializer(many=True, read_only=True)
    vendor_details = serializers.SerializerMethodField()
    buyer_details = serializers.SerializerMethodField()
    payment_method = serializers.CharField(source='parent_order.payment_method', read_only=True)
    payment_status = serializers.CharField(source='parent_order.payment_status', read_only=True)
    grand_total = serializers.SerializerMethodField()
    
    class Meta:
        model = VendorOrder
        fields = [
            'id',
            'vendor_order_number',
            'status',
            'parent_order',
            'vendor_shop',
            'payment_method',
            'payment_status',
            'subtotal_amount',
            'delivery_charge',
            'grand_total',
            'is_restocked',
            'restocked_at',
            'created_at',
            'updated_at',
            'vendor_details',
            'buyer_details',
            'vendor_order_items',
        ]
        read_only_fields = ['parent_order', 'vendor_shop', 'vendor_order_number', 'subtotal_amount', 'is_restocked', 'restocked_at', 'created_at', 'updated_at']

    def get_vendor_details(self, obj):
        shop = obj.vendor_shop
        return {
            "id": shop.id,
            "shop_name": shop.shop_name,
            "shop_address": shop.shop_address,
            "contact_email": shop.contact_email,
            "owner_phone": shop.user.phone_number
        }

    def get_buyer_details(self, obj):
        buyer = obj.parent_order.buyer
        return {
            "id": buyer.id,
            "full_name": buyer.full_name,
            "phone_number": buyer.phone_number,
            "shipping_address": obj.parent_order.shipping_address,
            "contact_phone": obj.parent_order.contact_phone
        }

    def get_grand_total(self, obj):
        return obj.subtotal_amount + obj.delivery_charge

class OrderSerializer(serializers.ModelSerializer):
    buyer_name = serializers.CharField(source='buyer.full_name', read_only=True)
    buyer_city_name = serializers.CharField(source='buyer_city.name', read_only=True)
    pickup_city_name = serializers.CharField(source='pickup_city.name', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    vendor_orders = VendorOrderSerializer(many=True, read_only=True)
    delivery_charge_breakdown = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            # 1. Primary Order Summary
            'id',
            'order_number',
            'status',
            'payment_method',
            'payment_status',
            'total_amount',
            'total_delivery_charge',
            'grand_total',
            'fulfillment_type',
            'rejection_reason',
            
            # 2. Buyer & Shipping Information
            'buyer',
            'buyer_name',
            'contact_phone',
            'shipping_address',
            'buyer_city',
            'buyer_city_name',
            
            # 3. Pickup & Hub Information
            'pickup_address',
            'pickup_phone',
            'pickup_city',
            'pickup_city_name',
            
            # 4. Pathao Courier Details
            'pathao_store_id',
            'pathao_consignment_id',
            'pathao_tracking_code',
            'pathao_order_status',
            'pathao_delivery_fee',
            'pathao_recipient_city_id',
            'pathao_recipient_zone_id',
            'pathao_recipient_area_id',
            
            # 5. Return & Restock Details
            'is_restocked',
            'restocked_at',

            # 6. Timestamps
            'created_at',
            'updated_at',
            
            # 7. Nested Lists & Breakdowns (Bottom)
            'delivery_charge_breakdown',
            'items',
            'vendor_orders',
        ]
        read_only_fields = [
            'buyer', 'order_number', 'total_amount', 'total_delivery_charge', 
            'fulfillment_type', 'status', 'payment_status', 'rejection_reason',
            'pathao_consignment_id', 'pathao_tracking_code', 'pathao_delivery_fee',
            'pathao_order_status', 'is_restocked', 'restocked_at', 'created_at', 'updated_at'
        ]

    def get_delivery_charge_breakdown(self, obj):
        breakdown = []
        if obj.vendor_orders.exists():
            for v_order in obj.vendor_orders.all():
                breakdown.append({
                    "shop_name": v_order.vendor_shop.shop_name,
                    "delivery_charge": v_order.delivery_charge
                })
        else:
            breakdown.append({
                "source": "Pathao Courier Dynamic Fee",
                "delivery_charge": obj.total_delivery_charge
            })
        return breakdown

    def get_grand_total(self, obj):
        return obj.total_amount + obj.total_delivery_charge


from vendors.models import City

class CheckoutSerializer(serializers.Serializer):
    shipping_address = serializers.CharField(required=False, allow_blank=True, help_text="Buyer shipping address (falls back to saved user address)")
    contact_phone = serializers.CharField(required=False, allow_blank=True, help_text="Buyer contact phone (falls back to account phone)")
    buyer_city = serializers.PrimaryKeyRelatedField(queryset=City.objects.all(), required=False, allow_null=True, help_text="Buyer city ID (optional)")
    pathao_recipient_city_id = serializers.IntegerField(required=False, allow_null=True, help_text="Pathao City ID (e.g. 1 for Dhaka)")
    pathao_recipient_zone_id = serializers.IntegerField(required=False, allow_null=True, help_text="Pathao Zone ID (e.g. 101 for Dhanmondi)")
    pathao_recipient_area_id = serializers.IntegerField(required=False, allow_null=True, help_text="Pathao Area ID")
    payment_method = serializers.ChoiceField(choices=Order.PAYMENT_METHOD_CHOICES, default='COD')

class AdminOrderApproveSerializer(serializers.Serializer):
    # Pickup Overrides
    pickup_address = serializers.CharField(required=False, allow_blank=True, help_text="Custom pickup address for courier collection")
    pickup_phone = serializers.CharField(required=False, allow_blank=True, help_text="Custom pickup phone number")
    pickup_city = serializers.PrimaryKeyRelatedField(queryset=City.objects.all(), required=False, allow_null=True, help_text="Custom pickup city ID")
    pathao_store_id = serializers.CharField(required=False, allow_blank=True, help_text="Pathao Pickup Store ID override")

    # Delivery / Recipient Overrides
    shipping_address = serializers.CharField(required=False, allow_blank=True, help_text="Buyer delivery address override")
    contact_phone = serializers.CharField(required=False, allow_blank=True, help_text="Buyer contact phone override")
    pathao_recipient_city_id = serializers.IntegerField(required=False, allow_null=True, help_text="Pathao Recipient City ID override")
    pathao_recipient_zone_id = serializers.IntegerField(required=False, allow_null=True, help_text="Pathao Recipient Zone ID override")
    pathao_recipient_area_id = serializers.IntegerField(required=False, allow_null=True, help_text="Pathao Recipient Area ID override")
    recalculate_delivery_charge = serializers.BooleanField(default=True, help_text="Recalculate delivery fee via Pathao if destination/store is updated")


class PathaoCalculatePriceSerializer(serializers.Serializer):
    store_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, help_text="Pathao Store ID")
    recipient_city = serializers.IntegerField(default=1, help_text="Recipient Pathao City ID")
    recipient_zone = serializers.IntegerField(default=101, help_text="Recipient Pathao Zone ID")
    weight = serializers.DecimalField(max_digits=5, decimal_places=2, default=0.5, help_text="Weight in KG")
    item_type = serializers.IntegerField(default=1, help_text="1: Document, 2: Parcel, 3: Fragile")
    delivery_type = serializers.IntegerField(default=48, help_text="48: Normal, 12: On Demand")

class PathaoDispatchSerializer(serializers.Serializer):
    item_weight = serializers.DecimalField(max_digits=5, decimal_places=2, default=0.5, help_text="Parcel weight in KG (e.g. 1.0)")
    item_quantity = serializers.IntegerField(default=1, min_value=1, help_text="Quantity of items")
    special_instruction = serializers.CharField(required=False, allow_blank=True, default="Handle with care", help_text="Special instructions for rider")

class VendorOrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=VendorOrder.STATUS_CHOICES,
        default='PACKED',
        help_text="Updated status for this sub-order (e.g. PROCESSING, PACKED, SHIPPED, DELIVERED, CANCELLED)"
    )

class PathaoWebhookEventSerializer(serializers.Serializer):
    consignment_id = serializers.CharField(required=False, default="PTH-CS-000001", help_text="Pathao Consignment ID")
    merchant_order_id = serializers.CharField(required=False, allow_blank=True, default="ORD-000001", help_text="ACCS Order Number")
    order_status = serializers.ChoiceField(
        choices=["Pickup_Pending", "In_Transit", "Delivered", "Returned", "Cancelled"],
        default="Delivered",
        help_text="Pathao event status"
    )





from .models import OrderCommission

class OrderCommissionSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source='order_item.product.title', read_only=True)
    quantity = serializers.IntegerField(source='order_item.quantity', read_only=True)
    
    order_details = serializers.SerializerMethodField()
    buyer_details = serializers.SerializerMethodField()
    vendor_details = serializers.SerializerMethodField()
    calculation_details = serializers.SerializerMethodField()

    class Meta:
        model = OrderCommission
        fields = ['id', 'order_item', 'product_title', 'quantity', 'commission_amount', 
                  'order_details', 'buyer_details', 'vendor_details', 'calculation_details', 
                  'created_at', 'updated_at']

    def get_order_details(self, obj):
        order = obj.order_item.order
        return {
            "order_number": order.order_number,
            "status": order.status,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status
        }

    def get_buyer_details(self, obj):
        buyer = obj.order_item.order.buyer
        return {
            "id": buyer.id,
            "full_name": buyer.full_name,
            "phone_number": buyer.phone_number,
            "shipping_address": obj.order_item.order.shipping_address
        }

    def get_vendor_details(self, obj):
        shop = obj.order_item.shop
        return {
            "id": shop.id,
            "shop_name": shop.shop_name,
            "shop_address": shop.shop_address,
            "owner_phone": shop.user.phone_number if shop.user else None
        }

    def get_calculation_details(self, obj):
        if obj.applied_percentage > 0:
            return {
                "type": "PERCENTAGE",
                "rate": str(obj.applied_percentage),
                "formula": "(Unit Price * Quantity) * Percentage",
                "calculation": f"({obj.order_item.unit_price} * {obj.order_item.quantity}) * {obj.applied_percentage}% = {obj.commission_amount}"
            }
        elif obj.applied_flat > 0:
            return {
                "type": "FLAT",
                "rate": str(obj.applied_flat),
                "formula": "Flat Rate * Quantity",
                "calculation": f"{obj.applied_flat} * {obj.order_item.quantity} = {obj.commission_amount}"
            }
        return {
            "type": "NONE",
            "rate": "0.00",
            "formula": "No commission setting found",
            "calculation": "0.00"
        }
