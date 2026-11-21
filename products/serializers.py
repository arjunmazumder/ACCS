from rest_framework import serializers
from .models import Category, Product, ProductImage, ProductReview

class CategoryChildSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'description', 'image', 'position', 'created_at', 'updated_at')

class CategoryTreeSerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'description', 'image', 'position', 'subcategories', 'created_at', 'updated_at')

    def get_subcategories(self, obj):
        children = obj.subcategories.all().order_by('position', 'name')
        return CategoryTreeSerializer(children, many=True, context=self.context).data

class CategorySerializer(serializers.ModelSerializer):
    subcategories = CategoryChildSerializer(many=True, read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    ancestors = serializers.SerializerMethodField(help_text='Parent chain from the top-level category down to the direct parent')

    class Meta:
        model = Category
        fields = ('id', 'parent', 'parent_name', 'ancestors', 'name', 'description', 'image', 'position', 'subcategories', 'created_at', 'updated_at')
        read_only_fields = ['created_at', 'updated_at']

    def get_ancestors(self, obj):
        return [{'id': a.id, 'name': a.name} for a in obj.ancestors]

    def validate_parent(self, parent):
        if parent is None:
            return parent
        instance = self.instance
        if instance is not None and (parent.pk == instance.pk or instance.pk in [a.pk for a in parent.ancestors]):
            raise serializers.ValidationError('A category cannot be placed inside itself or one of its own sub-categories.')
        # Depth of the deepest branch being moved under `parent`
        subtree_depth = 1
        if instance is not None:
            level, frontier = 1, [instance.pk]
            while True:
                frontier = list(Category.objects.filter(parent_id__in=frontier).values_list('id', flat=True))
                if not frontier:
                    break
                level += 1
            subtree_depth = level
        if parent.depth + subtree_depth > Category.MAX_DEPTH:
            raise serializers.ValidationError(
                f'Categories can be at most {Category.MAX_DEPTH} levels deep (category → sub-category → sub-sub-category).'
            )
        return parent

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = '__all__'
        read_only_fields = ['created_at']

PREVIEW_PDF_MAX_MB = 15


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

    def _update_with_images(self, instance, validated_data):
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

    def validate_preview_pdf(self, file):
        """Sample pages must be a real PDF (checked by its header) of at most PREVIEW_PDF_MAX_MB."""
        if not file:
            return file
        if not file.name.lower().endswith('.pdf'):
            raise serializers.ValidationError('Upload the preview as a PDF file.')
        if file.size > PREVIEW_PDF_MAX_MB * 1024 * 1024:
            raise serializers.ValidationError(f'The preview PDF must be {PREVIEW_PDF_MAX_MB} MB or smaller.')
        head = file.read(5)
        file.seek(0)
        if head != b'%PDF-':
            raise serializers.ValidationError('This file is not a valid PDF.')
        return file

    def update(self, instance, validated_data):
        # Replacing or removing the preview deletes the old file from storage
        if 'preview_pdf' in validated_data and instance.preview_pdf and validated_data['preview_pdf'] != instance.preview_pdf:
            instance.preview_pdf.delete(save=False)
        return self._update_with_images(instance, validated_data)

    def get_after_discount_price(self, obj):
        from django.utils import timezone
        
        base_price = obj.price
        
        if not base_price:
            return None
            
        if obj.discount_type == 'NONE' or not obj.discount_value:
            return None
            
        # Check if discount dates are valid
        now = timezone.now()
        if obj.discount_end_date and now > obj.discount_end_date:
            return None
        if obj.discount_start_date and obj.discount_start_date.date() > now.date():
            return None
                
        # Calculate discount
        if obj.discount_type == 'FLAT':
            return round(max(0.0, float(base_price) - float(obj.discount_value)), 2)
        elif obj.discount_type == 'PERCENTAGE':
            discount_amount = float(base_price) * (float(obj.discount_value) / 100)
            return round(max(0.0, float(base_price) - discount_amount), 2)
            
        return None
    
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['shop', 'approval_status', 'rejection_reason', 'rating_avg', 'rating_count', 'created_at', 'updated_at']

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



class ProductReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ProductReview
        fields = ('id', 'product', 'user', 'user_name', 'rating', 'comment', 'created_at')
        read_only_fields = ('user', 'created_at')

    def get_user_name(self, obj):
        name = (obj.user.full_name or '').strip()
        return name or f"Buyer {obj.user.phone_number[-3:]}"

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value
