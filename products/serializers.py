from rest_framework import serializers
from .models import Category, Product, ProductImage

class CategoryChildSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'description', 'image', 'created_at', 'updated_at')

class CategoryTreeSerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'description', 'image', 'subcategories', 'created_at', 'updated_at')

    def get_subcategories(self, obj):
        children = obj.subcategories.all().order_by('name')
        return CategoryTreeSerializer(children, many=True, context=self.context).data

class CategorySerializer(serializers.ModelSerializer):
    subcategories = CategoryChildSerializer(many=True, read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)

    class Meta:
        model = Category
        fields = ('id', 'parent', 'parent_name', 'name', 'description', 'image', 'subcategories', 'created_at', 'updated_at')
        read_only_fields = ['created_at', 'updated_at']

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = '__all__'
        read_only_fields = ['created_at']

class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(max_length=100000, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False,
        help_text="Upload one or multiple images for the product during creation"
    )
    category_name = serializers.CharField(source='category.name', read_only=True)
    after_discount_price = serializers.SerializerMethodField()
    shop_name = serializers.CharField(source='shop.shop_name', read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    def create(self, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        product = super().create(validated_data)
        for i, img in enumerate(uploaded_images):
            ProductImage.objects.create(product=product, image=img, is_primary=(i == 0))
        return product

    def update(self, instance, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        product = super().update(instance, validated_data)
        has_primary = product.images.filter(is_primary=True).exists()
        for i, img in enumerate(uploaded_images):
            ProductImage.objects.create(product=product, image=img, is_primary=(not has_primary and i == 0))
        return product

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user and request.user.is_authenticated:
            user = request.user
            is_admin = user.is_staff or user.is_superuser or (hasattr(user, 'role') and user.role and user.role.name == 'ROLE' and user.role.value == 'ADMIN')
            if not is_admin:
                self.fields['approval_status'].read_only = True
                self.fields['rejection_reason'].read_only = True
                # Platform commission is set by admins only
                self.fields['woner_commission'].read_only = True

    def get_after_discount_price(self, obj):
        from django.utils import timezone
        
        base_price = obj.price
        
        if not base_price:
            return None
            
        if obj.discount_type == 'NONE' or not obj.discount_value:
            return None
            
        # Check if discount dates are valid
        now = timezone.now()
        if obj.discount_start_date and obj.discount_end_date:
            if not (obj.discount_start_date <= now <= obj.discount_end_date):
                return None
                
        # Calculate discount
        if obj.discount_type == 'FLAT':
            return max(0.0, float(base_price) - float(obj.discount_value))
        elif obj.discount_type == 'PERCENTAGE':
            discount_amount = float(base_price) * (float(obj.discount_value) / 100)
            return max(0.0, float(base_price) - discount_amount)
            
        return None
    
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['shop', 'approval_status', 'rejection_reason', 'created_at', 'updated_at']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Move dynamic/nested fields to the bottom of the JSON response
        after_discount = representation.pop('after_discount_price', None)
        images = representation.pop('images', [])
        
        representation['after_discount_price'] = after_discount
        representation['images'] = images
        
        # Category Details
        if instance.category:
            representation['category_details'] = CategorySerializer(instance.category, context=self.context).data
        else:
            representation['category_details'] = None

        # Shop Details
        if instance.shop:
            from vendors.serializers import ShopProfileSerializer
            shop_data = ShopProfileSerializer(instance.shop, context=self.context).data
            representation['shop_details'] = shop_data.get('shop_details', shop_data)
        else:
            representation['shop_details'] = None

        return representation

    def to_internal_value(self, data):
        # Convert empty strings to None for Decimal fields to prevent "A valid number is required" error
        for field in ['price', 'discount_value', 'woner_commission']:
            if field in data and data[field] == '':
                # Ensure the data dictionary is mutable, handle QueryDict from form-data
                if hasattr(data, '_mutable'):
                    data._mutable = True
                data[field] = None
        return super().to_internal_value(data)

class ProductRejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional reason for rejecting the product"
    )

