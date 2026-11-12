from django.utils.text import slugify
from rest_framework import serializers

from products.models import Product
from products.serializers import ProductImageSerializer
from .models import Banner, Coupon, LandingPage, LandingPageItem


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def to_internal_value(self, data):
        # Multipart forms send '' for cleared optional dates
        if hasattr(data, 'copy'):
            data = data.copy()
            for key in ('starts_at', 'ends_at'):
                if data.get(key) == '':
                    data[key] = None
        return super().to_internal_value(data)


class LandingProductSerializer(serializers.ModelSerializer):
    """Compact product payload for landing pages."""
    images = ProductImageSerializer(many=True, read_only=True)
    after_discount_price = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    shop_name = serializers.CharField(source='shop.shop_name', read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'title', 'author', 'publisher', 'price', 'after_discount_price', 'stock_quantity', 'moq',
                  'images', 'category_name', 'shop_name', 'is_active', 'approval_status')

    def get_after_discount_price(self, obj):
        from orders.utils import calculate_product_unit_price
        price = calculate_product_unit_price(obj, 1)
        return float(price) if obj.price and price < obj.price else None


class LandingPageItemSerializer(serializers.ModelSerializer):
    product = LandingProductSerializer(read_only=True)

    class Meta:
        model = LandingPageItem
        fields = ('id', 'product', 'position', 'is_preselected')


class LandingPageSerializer(serializers.ModelSerializer):
    items = LandingPageItemSerializer(many=True, read_only=True)
    product_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False,
                                        help_text='Products in display order')
    preselected_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False,
                                            help_text='Products ticked by default')
    order_count = serializers.SerializerMethodField()
    slug = serializers.SlugField(required=False, allow_blank=True)

    class Meta:
        model = LandingPage
        fields = ('id', 'title', 'slug', 'headline', 'description', 'banner_image', 'theme_color', 'cta_text',
                  'is_active', 'starts_at', 'ends_at', 'items', 'product_ids', 'preselected_ids', 'order_count',
                  'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

    def get_order_count(self, obj):
        return obj.orders.count()

    def to_internal_value(self, data):
        if hasattr(data, 'getlist'):
            # multipart: lists arrive as repeated keys or a comma-separated string
            plain = {k: data.get(k) for k in data.keys()}
            for key in ('product_ids', 'preselected_ids'):
                values = data.getlist(key)
                if len(values) == 1 and ',' in str(values[0]):
                    values = values[0].split(',')
                plain[key] = [v for v in values if str(v).strip()]
            for key in ('starts_at', 'ends_at'):
                if plain.get(key) == '':
                    plain[key] = None
            if 'banner_image' in data:
                plain['banner_image'] = data.get('banner_image') or None
            data = plain
        return super().to_internal_value(data)

    def validate(self, attrs):
        if not attrs.get('slug') and not (self.instance and self.instance.slug):
            base = slugify(attrs.get('title') or '') or 'offer'
            slug, n = base, 2
            while LandingPage.objects.filter(slug=slug).exclude(pk=getattr(self.instance, 'pk', None)).exists():
                slug, n = f'{base}-{n}', n + 1
            attrs['slug'] = slug
        elif attrs.get('slug') == '':
            attrs.pop('slug')
        return attrs

    def _sync_items(self, page, product_ids, preselected_ids):
        if product_ids is None:
            if preselected_ids is not None:
                page.items.update(is_preselected=False)
                page.items.filter(product_id__in=preselected_ids).update(is_preselected=True)
            return
        valid = set(Product.objects.filter(id__in=product_ids).values_list('id', flat=True))
        ordered = [pid for pid in dict.fromkeys(product_ids) if pid in valid]
        page.items.exclude(product_id__in=ordered).delete()
        preselected = set(preselected_ids or [])
        for pos, pid in enumerate(ordered):
            LandingPageItem.objects.update_or_create(
                landing_page=page, product_id=pid,
                defaults={'position': pos, 'is_preselected': pid in preselected},
            )

    def create(self, validated_data):
        product_ids = validated_data.pop('product_ids', [])
        preselected_ids = validated_data.pop('preselected_ids', [])
        page = super().create(validated_data)
        self._sync_items(page, product_ids, preselected_ids)
        return page

    def update(self, instance, validated_data):
        product_ids = validated_data.pop('product_ids', None)
        preselected_ids = validated_data.pop('preselected_ids', None)
        page = super().update(instance, validated_data)
        self._sync_items(page, product_ids, preselected_ids)
        return page


class LandingOrderLineSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=999)


class LandingOrderSerializer(serializers.Serializer):
    items = LandingOrderLineSerializer(many=True)
    full_name = serializers.CharField(max_length=255)
    phone_number = serializers.RegexField(r'^01[3-9]\d{8}$', error_messages={'invalid': 'Enter a valid 11-digit mobile number (01XXXXXXXXX).'})
    address = serializers.CharField(max_length=500)
    pathao_city_id = serializers.IntegerField(required=False, allow_null=True)
    pathao_zone_id = serializers.IntegerField(required=False, allow_null=True)
    pathao_area_id = serializers.IntegerField(required=False, allow_null=True)
    location_label = serializers.CharField(required=False, allow_blank=True, max_length=255)
    coupon_code = serializers.CharField(required=False, allow_blank=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = '__all__'
        read_only_fields = ['times_used', 'created_at']


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
