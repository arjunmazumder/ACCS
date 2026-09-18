from rest_framework import serializers
from .models import ShopProfile, ShopReview, City
from users.serializers import UserSerializer

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = '__all__'

class ShopProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopProfile
        fields = '__all__'
        read_only_fields = ['user', 'average_rating', 'total_reviews', 'admin_rating_adjustment', 'is_blocked', 'created_at', 'updated_at']

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.method == 'POST':
            user = request.user
            if user and user.is_authenticated:
                if hasattr(user, 'vendor_shop_profile') or ShopProfile.objects.filter(user=user).exists():
                    raise serializers.ValidationError({"detail": "A shop profile already exists for this user. Please use PUT or PATCH to update it."})
        return attrs

    def to_representation(self, instance):
        base_data = super().to_representation(instance)
        
        city_data = None
        if instance.city:
            city_data = CitySerializer(instance.city).data
            
        user_data = None
        if instance.user:
            user_data = UserSerializer(instance.user).data

        shop_details = {
            "id": instance.id,
            "shop_type": instance.shop_type,
            "shop_name": instance.shop_name,
            "description": instance.description,
            "logo": base_data.get("logo"),
            "banner": base_data.get("banner"),
            "contact_email": instance.contact_email,
            "city": city_data,
            "shop_address": instance.shop_address,
            "pathao_store_id": instance.pathao_store_id,
            "trade_license_number": instance.trade_license_number,
            "trade_license_document": base_data.get("trade_license_document"),
            "opening_time": str(instance.opening_time) if instance.opening_time else None,
            "closing_time": str(instance.closing_time) if instance.closing_time else None,
            "average_rating": instance.average_rating,
            "total_reviews": instance.total_reviews,
            "admin_rating_adjustment": instance.admin_rating_adjustment,
            "is_blocked": instance.is_blocked,
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
        }

        return {
            "shop_details": shop_details,
            "user_details": user_data
        }

class ShopReviewSerializer(serializers.ModelSerializer):
    reviewer_phone = serializers.CharField(source='reviewer.phone_number', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.full_name', read_only=True)
    average_rating = serializers.FloatField(read_only=True)

    class Meta:
        model = ShopReview
        fields = '__all__'
        read_only_fields = ['reviewer', 'created_at']

    def validate(self, attrs):
        request = self.context.get('request')
        shop = attrs.get('shop')

        if request and request.user:
            # Check if user is trying to review their own shop
            if shop and shop.user == request.user:
                raise serializers.ValidationError({"error": "You cannot review your own shop."})
                
        return attrs


