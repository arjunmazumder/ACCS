from rest_framework import serializers
from .models import Wallet, WalletTransaction

class WalletSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField()
    shop_profile = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ['id', 'balance', 'credit_limit', 'created_at', 'updated_at', 'user_info', 'shop_profile']
        read_only_fields = ['id', 'balance', 'credit_limit', 'created_at', 'updated_at']

    def get_user_info(self, obj):
        user = obj.user
        return {
            "id": user.id,
            "phone_number": user.phone_number,
            "full_name": user.full_name,
            "role": user.role.value if user.role else None,
            "is_approved": user.is_approved,
            "is_phone_verified": user.is_phone_verified,
        }

    def get_shop_profile(self, obj):
        if hasattr(obj.user, 'vendor_shop_profile'):
            shop = obj.user.vendor_shop_profile
            return {
                "id": shop.id,
                "shop_name": shop.shop_name,
                "shop_type": shop.shop_type,
                "shop_address": shop.shop_address,
                "contact_email": shop.contact_email,
                "city_name": shop.city.name if shop.city else None,
                "pathao_store_id": shop.pathao_store_id,
                "is_blocked": shop.is_blocked,
                "average_rating": shop.average_rating,
                "total_reviews": shop.total_reviews,
            }
        return None


class WalletTransactionSerializer(serializers.ModelSerializer):
    order_details = serializers.SerializerMethodField()

    class Meta:
        model = WalletTransaction
        fields = [
            'id', 
            'transaction_type', 
            'amount', 
            'discount',
            'order_commission', 
            'description', 
            'created_at',
            'order_details'
        ]
        read_only_fields = fields

    def get_order_details(self, obj):
        if not obj.order_commission:
            return None
        item = obj.order_commission.order_item
        if not item:
            return None
            
        buyer = item.order.buyer
        vendor = item.shop
        
        return {
            'order_id': item.order.id,
            'order_number': item.order.order_number,
            'buyer': {
                'id': buyer.id,
                'name': buyer.full_name,
                'phone': buyer.phone_number
            },
            'vendor': {
                'id': vendor.id,
                'shop_name': vendor.shop_name
            },
            'item': {
                'product_name': item.product.title if item.product else 'Unknown',
                'quantity': item.quantity,
                'unit_price': str(item.unit_price)
            },
            'commission_applied': {
                'percentage': str(obj.order_commission.applied_percentage),
                'flat': str(obj.order_commission.applied_flat)
            }
        }

class UpdateCreditLimitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['credit_limit']

from decimal import Decimal

class AddDiscountSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
