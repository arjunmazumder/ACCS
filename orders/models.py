from django.db import models
from django.contrib.auth import get_user_model
from products.models import Product
from vendors.models import ShopProfile

User = get_user_model()

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='cart')
    guest_id = models.CharField(max_length=255, null=True, blank=True, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.user:
            return f"Cart of {self.user.phone_number}"
        return f"Guest Cart ({self.guest_id})"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('cart', 'product')

    def __str__(self):
        return f"{self.quantity} x {self.product.title} in Cart {self.cart.id}"

class Order(models.Model):
    STATUS_CHOICES = (
        ('PENDING_ADMIN_APPROVAL', 'Pending Admin Approval'),
        ('APPROVED', 'Approved (Sent to Vendor)'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('RETURNED', 'Returned'),
    )
    PAYMENT_METHOD_CHOICES = (
        ('COD', 'Cash on Delivery'),
        ('ONLINE', 'Online Payment'),
    )
    PAYMENT_STATUS_CHOICES = (
        ('UNPAID', 'Unpaid'),
        ('PAID', 'Paid'),
    )
    FULFILLMENT_TYPE_CHOICES = (
        ('DIRECT_VENDOR', 'Direct Vendor Pickup'),
        ('CENTRAL_HUB', 'Central Hub Aggregation'),
    )

    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    buyer_city = models.ForeignKey('vendors.City', on_delete=models.SET_NULL, null=True, blank=True)
    order_number = models.CharField(max_length=50, unique=True, blank=True)
    
    # Shipping details
    shipping_address = models.TextField()
    contact_phone = models.CharField(max_length=20)
    
    # Hybrid Fulfillment & Pickup details
    fulfillment_type = models.CharField(max_length=20, choices=FULFILLMENT_TYPE_CHOICES, default='DIRECT_VENDOR')
    pickup_address = models.TextField(blank=True, null=True, help_text="Pickup location where courier collects parcel")
    pickup_phone = models.CharField(max_length=20, blank=True, null=True)
    pickup_city = models.ForeignKey('vendors.City', on_delete=models.SET_NULL, null=True, blank=True, related_name='pickup_orders')

    # Pathao Specific Fields
    pathao_store_id = models.CharField(max_length=100, blank=True, null=True, help_text="Pathao Pickup Store ID")
    pathao_recipient_city_id = models.IntegerField(blank=True, null=True)
    pathao_recipient_zone_id = models.IntegerField(blank=True, null=True)
    pathao_recipient_area_id = models.IntegerField(blank=True, null=True)

    pathao_consignment_id = models.CharField(max_length=100, blank=True, null=True)
    pathao_tracking_code = models.CharField(max_length=100, blank=True, null=True)
    pathao_delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pathao_order_status = models.CharField(max_length=50, blank=True, null=True)
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='PENDING_ADMIN_APPROVAL')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='COD')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='UNPAID')
    
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Return & Restock Inventory Tracking
    is_restocked = models.BooleanField(default=False, help_text="True if returned/cancelled items have been restocked to inventory")
    restocked_at = models.DateTimeField(null=True, blank=True)
    restocked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='restocked_orders')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.order_number:
            self.order_number = f"ORD-{self.id:06d}"
            super().save(update_fields=['order_number'])
            
        # --- COMMISSION AND VENDOR ORDER LOGIC ---
        if self.status == 'APPROVED':
            from decimal import Decimal
            from .models import OrderCommission, VendorOrder, DeliveryCharge
            
            # --- VENDOR ORDER CREATION ---
            if not self.vendor_orders.exists():
                shop_items = {}
                for item in self.items.all():
                    if item.shop not in shop_items:
                        shop_items[item.shop] = []
                    shop_items[item.shop].append(item)

                for shop, items in shop_items.items():
                    subtotal = sum(i.quantity * i.unit_price for i in items)
                    
                    delivery_charge = Decimal('0.00')
                    if len(shop_items) == 1:
                        delivery_charge = Decimal(str(self.total_delivery_charge))
                    elif len(shop_items) > 1:
                        delivery_charge = (Decimal(str(self.total_delivery_charge)) / Decimal(str(len(shop_items)))).quantize(Decimal('0.01'))
                            
                    vendor_order = VendorOrder.objects.create(

                        parent_order=self,
                        vendor_shop=shop,
                        subtotal_amount=subtotal,
                        delivery_charge=delivery_charge,
                        status='PROCESSING'
                    )
                    
                    for item in items:
                        item.vendor_order = vendor_order
                        item.save(update_fields=['vendor_order'])
                        
                        # Deduct stock ONLY upon approval
                        if item.product:
                            item.product.stock_quantity -= item.quantity
                            item.product.save(update_fields=['stock_quantity', 'updated_at'])
            
            # --- COMMISSION LOGIC ---
            
            for item in self.items.all():
                product_comm_pct = Decimal('0.00')
                if item.product and item.product.woner_commission is not None:
                    product_comm_pct = Decimal(str(item.product.woner_commission))
                    
                item_total = item.unit_price * item.quantity
                calculated_commission = (item_total * product_comm_pct) / Decimal('100.00')
                        
                order_comm, created = OrderCommission.objects.get_or_create(order_item=item)
                
                new_applied_pct = product_comm_pct
                new_applied_flat = Decimal('0.00')
                
                if Decimal(str(order_comm.commission_amount)) != calculated_commission or Decimal(str(order_comm.applied_percentage)) != new_applied_pct or Decimal(str(order_comm.applied_flat)) != new_applied_flat:
                    current_comm = Decimal(str(order_comm.commission_amount))
                    difference = calculated_commission - current_comm
                    order_comm.commission_amount = calculated_commission
                    order_comm.applied_percentage = new_applied_pct
                    order_comm.applied_flat = new_applied_flat
                    order_comm.save(update_fields=['commission_amount', 'applied_percentage', 'applied_flat', 'updated_at'])
                    
                    if difference != Decimal('0.00') and item.shop and item.shop.user:
                        from wallets.models import Wallet, WalletTransaction
                        wallet, _ = Wallet.objects.get_or_create(user=item.shop.user)
                        
                        current_balance = Decimal(str(wallet.balance))
                        wallet.balance = current_balance - difference
                        wallet.save(update_fields=['balance', 'updated_at'])
                        WalletTransaction.objects.create(
                            wallet=wallet,
                            transaction_type='OUT' if difference > 0 else 'IN',
                            amount=abs(difference),
                            order_commission=order_comm,
                            description=f"Commission adjustment for Order {self.order_number}"
                        )

    def __str__(self):
        return f"Order {self.order_number} by {self.buyer.phone_number}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    shop = models.ForeignKey(ShopProfile, on_delete=models.CASCADE, related_name='order_items')
    
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Optional VendorOrder connection if we link OrderItem to VendorOrder directly
    vendor_order = models.ForeignKey('VendorOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='vendor_order_items')

    def __str__(self):
        product_title = self.product.title if self.product else "Deleted Product"
        return f"{self.quantity} x {product_title} in Order {self.order.order_number}"

class VendorOrder(models.Model):
    STATUS_CHOICES = (
        ('PROCESSING', 'Processing'),
        ('PACKED', 'Packed'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
        ('RETURNED', 'Returned'),
    )
    parent_order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='vendor_orders')
    vendor_shop = models.ForeignKey(ShopProfile, on_delete=models.CASCADE, related_name='vendor_orders')
    
    vendor_order_number = models.CharField(max_length=50, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROCESSING')
    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Return & Restock Tracking for Vendor Order
    is_restocked = models.BooleanField(default=False, help_text="True if returned items have been restocked to shop inventory")
    restocked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.vendor_order_number:
            self.vendor_order_number = f"VORD-{self.id:06d}"
            super().save(update_fields=['vendor_order_number'])

    def __str__(self):
        return f"Vendor Order {self.vendor_order_number} for {self.vendor_shop.shop_name}"

class DeliveryCharge(models.Model):
    inside_city = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    outside_city = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Central Hub Configuration
    hub_name = models.CharField(max_length=255, default="Central Warehouse")
    hub_address = models.TextField(default="Dhaka Central Hub, Bangladesh")
    hub_phone = models.CharField(max_length=20, default="01700000000")
    hub_city = models.ForeignKey('vendors.City', on_delete=models.SET_NULL, null=True, blank=True, related_name='delivery_hubs')
    pathao_hub_store_id = models.CharField(max_length=100, blank=True, null=True, help_text="Pathao Store ID for Central Hub")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Delivery Charges"

    def __str__(self):
        return f"Inside City: {self.inside_city}, Outside City: {self.outside_city}"

class OrderCommission(models.Model): 
    order_item = models.OneToOneField('OrderItem', on_delete=models.CASCADE, related_name='commission_record')
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    applied_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    applied_flat = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Commission for Item {self.order_item.id} - {self.commission_amount}"

