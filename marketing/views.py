import secrets

from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.filters import SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from lookup.models import Lookup
from orders.serializers import OrderSerializer
from orders.services.checkout import CheckoutError, place_order, resolve_coupon
from users.models import User
from users.permissions import IsAdminOrReadOnly, IsAdminOrSuperAdmin
from .models import Banner, Coupon, LandingPage, SiteSettings
from .serializers import (
    BannerSerializer, CouponSerializer, CouponValidateSerializer, LandingOrderSerializer, LandingPageSerializer,
    SiteSettingsSerializer,
)


def _is_staff(user):
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser or
                (user.role and user.role.name == 'ROLE' and user.role.value == 'ADMIN')))


@extend_schema(tags=['Marketing'])
class BannerViewSet(viewsets.ModelViewSet):
    """Home page slider. Shoppers get live banners only; admins manage all of them."""
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    serializer_class = BannerSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    pagination_class = None
    queryset = Banner.objects.all()

    def get_queryset(self):
        if _is_staff(self.request.user) and self.request.query_params.get('all') in ('1', 'true'):
            return Banner.objects.all()
        return Banner.objects.live()


@extend_schema(tags=['Marketing'])
class LandingPageViewSet(viewsets.ModelViewSet):
    """Admin management of landing pages (product bundles that can be ordered from one page)."""
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    serializer_class = LandingPageSerializer
    permission_classes = [IsAdminOrSuperAdmin]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    queryset = LandingPage.objects.prefetch_related('items__product__images', 'items__product__shop', 'items__product__category')
    filter_backends = [SearchFilter]
    search_fields = ['title', 'slug', 'headline']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema(tags=['Marketing'], summary='Public landing page by slug')
class PublicLandingPageView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        page = get_object_or_404(
            LandingPage.objects.live().prefetch_related('items__product__images', 'items__product__shop', 'items__product__category'),
            slug=slug,
        )
        return Response(LandingPageSerializer(page, context={'request': request}).data)


def _buyer_for(request, phone, full_name):
    """Logged-in shopper, otherwise the account for this phone (created on first order)."""
    if request.user and request.user.is_authenticated:
        return request.user, False
    user = User.objects.filter(phone_number=phone).first()
    if user:
        return user, False
    role, _ = Lookup.objects.get_or_create(name='ROLE', value='BUYER', defaults={'is_active': True})
    user = User.objects.create_user(
        phone_number=phone, password=secrets.token_urlsafe(16), full_name=full_name,
        role=role, is_approved=True, is_phone_verified=False,
    )
    user.groups.add(Group.objects.get_or_create(name='buyer')[0])
    return user, True


@extend_schema(tags=['Marketing'], summary='Place an order from a landing page (guests welcome)', request=LandingOrderSerializer)
class LandingOrderView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, slug):
        page = get_object_or_404(LandingPage.objects.live(), slug=slug)
        serializer = LandingOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        allowed = {item.product_id: item.product for item in page.items.select_related('product__shop', 'product__shop__user')}
        lines = []
        for line in data['items']:
            product = allowed.get(line['product_id'])
            if not product:
                return Response({'error': 'One of the selected products is not part of this offer.'}, status=status.HTTP_400_BAD_REQUEST)
            lines.append((product, line['quantity']))

        buyer, created = _buyer_for(request, data['phone_number'], data['full_name'])
        address = ', '.join(filter(None, [data['address'].strip(), data.get('location_label', '').strip()]))
        try:
            order = place_order(
                buyer=buyer, lines=lines,
                shipping_address=f"{data['full_name'].strip()} — {address}",
                contact_phone=data['phone_number'],
                recipient_city_id=data.get('pathao_city_id'),
                recipient_zone_id=data.get('pathao_zone_id'),
                recipient_area_id=data.get('pathao_area_id'),
                coupon_code=data.get('coupon_code'),
                source='LANDING', landing_page=page, note=data.get('note'),
            )
        except CheckoutError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': 'Order placed successfully. We will call you to confirm.',
            'account_created': created,
            'order': OrderSerializer(order).data,
        }, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Marketing'])
class CouponViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    serializer_class = CouponSerializer
    permission_classes = [IsAdminOrSuperAdmin]
    queryset = Coupon.objects.all()
    filter_backends = [SearchFilter]
    search_fields = ['code', 'description']


@extend_schema(tags=['Marketing'], summary='Check a coupon code against a subtotal', request=CouponValidateSerializer)
class CouponValidateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CouponValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            coupon, discount = resolve_coupon(serializer.validated_data['code'], serializer.validated_data['subtotal'])
        except CheckoutError as exc:
            return Response({'valid': False, 'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'valid': True, 'code': coupon.code, 'discount': discount, 'description': coupon.description})


@extend_schema(tags=['Marketing'], summary='Storefront contact details (WhatsApp button, hotline)', request=SiteSettingsSerializer, responses=SiteSettingsSerializer)
class SiteSettingsView(APIView):
    """Anyone can read; admins (or staff with the site settings permission) can update."""
    permission_classes = [IsAdminOrReadOnly]
    permission_model = SiteSettings

    def get(self, request):
        return Response(SiteSettingsSerializer(SiteSettings.load()).data)

    def patch(self, request):
        serializer = SiteSettingsSerializer(SiteSettings.load(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
