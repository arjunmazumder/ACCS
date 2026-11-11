from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from drf_spectacular.utils import extend_schema
from users.permissions import IsVendorOrReadOnly, IsAdminOrSuperAdmin, IsAdminOrReadOnly
from .models import City, ShopProfile, ShopReview
from .serializers import CitySerializer, ShopProfileSerializer, ShopReviewSerializer

def is_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    if hasattr(user, 'role') and user.role and user.role.name == 'ROLE' and user.role.value == 'ADMIN':
        return True
    return False

@extend_schema(tags=['Vendors'])
class CityViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [IsAdminOrReadOnly]
<<<<<<< HEAD
=======
    pagination_class = None
>>>>>>> d3f86bdf3dac8fc402d56ff1ebace7e1271c6a92

@extend_schema(tags=['Vendors'])
class ShopProfileViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = ShopProfile.objects.all()
    serializer_class = ShopProfileSerializer
    permission_classes = [IsVendorOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['shop_type', 'city']
    search_fields = ['shop_name', 'shop_address']

    def get_queryset(self):
        if is_admin(self.request.user):
            return ShopProfile.objects.all()
        return ShopProfile.objects.filter(is_blocked=False)

    def perform_create(self, serializer):
        user = self.request.user
        if not is_admin(user):
            if not user.role or user.role.value.upper() not in ['VENDOR', 'RETAILER', 'WHOLESALER']:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Only Vendors can create a shop profile.")
        if hasattr(user, 'vendor_shop_profile') or ShopProfile.objects.filter(user=user).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "A shop profile already exists for this user. Please use PATCH to update it."})
        serializer.save(user=user)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        shop = get_object_or_404(ShopProfile, user=request.user)
        return Response(ShopProfileSerializer(shop).data)

<<<<<<< HEAD
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        if not hasattr(request.user, 'vendor_shop_profile'):
            return Response({"error": "Only vendors with a shop profile can view shop dashboard."}, status=status.HTTP_403_FORBIDDEN)
        
        shop = request.user.vendor_shop_profile
        from orders.models import VendorOrder
        from products.models import Product
        from wallets.models import Wallet
        from django.db.models import Sum, F

        vendor_orders = VendorOrder.objects.filter(vendor_shop=shop)
        total_orders = vendor_orders.count()
        by_status = {}
        for st in ['PROCESSING', 'PACKED', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED']:
            by_status[st] = vendor_orders.filter(status=st).count()

        delivered_rev = vendor_orders.filter(status='DELIVERED').aggregate(total=Sum('subtotal_amount'))['total'] or 0.0
        pipeline_rev = vendor_orders.filter(status__in=['PROCESSING', 'PACKED', 'SHIPPED']).aggregate(total=Sum('subtotal_amount'))['total'] or 0.0

        products = Product.objects.filter(shop=shop)
        approved_prods = products.filter(approval_status='APPROVED').count()
        pending_prods = products.filter(approval_status='PENDING').count()
        low_stock_prods = products.filter(stock_quantity__gt=0, stock_quantity__lte=F('low_stock_threshold')).count()
        out_of_stock_prods = products.filter(stock_quantity__lte=0).count()

        wallet = Wallet.objects.filter(user=request.user).first()
        wallet_balance = float(wallet.balance) if wallet else 0.0
        credit_limit = float(wallet.credit_limit) if wallet else 2000.0

        return Response({
            "revenue": {
                "delivered": float(delivered_rev),
                "pipeline": float(pipeline_rev)
            },
            "orders": {
                "total": total_orders,
                "by_status": by_status
            },
            "products": {
                "approved": approved_prods,
                "pending": pending_prods,
                "low_stock": low_stock_prods,
                "out_of_stock": out_of_stock_prods
            },
            "wallet": {
                "balance": wallet_balance,
                "credit_limit": credit_limit
            },
            "shop": {
                "average_rating": shop.average_rating,
                "total_reviews": shop.total_reviews
            }
=======
    @extend_schema(summary="Vendor dashboard statistics for the logged-in shop owner")
    @action(detail=False, methods=['get'], url_path='me/dashboard', permission_classes=[permissions.IsAuthenticated])
    def dashboard(self, request):
        from django.db.models import Sum, Count, F
        from products.models import Product
        from orders.models import VendorOrder
        from wallets.models import Wallet

        shop = get_object_or_404(ShopProfile, user=request.user)
        products = Product.objects.filter(shop=shop)
        vendor_orders = VendorOrder.objects.filter(vendor_shop=shop)
        wallet, _ = Wallet.objects.get_or_create(user=request.user)

        status_counts = {row['status']: row['count'] for row in vendor_orders.values('status').annotate(count=Count('id'))}
        delivered_revenue = vendor_orders.filter(status='DELIVERED').aggregate(total=Sum('subtotal_amount'))['total'] or 0
        pipeline_revenue = vendor_orders.exclude(status__in=['CANCELLED', 'RETURNED']).aggregate(total=Sum('subtotal_amount'))['total'] or 0

        return Response({
            "shop": {"id": shop.id, "shop_name": shop.shop_name, "is_blocked": shop.is_blocked,
                     "average_rating": shop.average_rating, "total_reviews": shop.total_reviews},
            "products": {
                "total": products.count(),
                "approved": products.filter(approval_status='APPROVED').count(),
                "pending": products.filter(approval_status='PENDING').count(),
                "rejected": products.filter(approval_status='REJECTED').count(),
                "low_stock": products.filter(stock_quantity__gt=0, stock_quantity__lte=F('low_stock_threshold')).count(),
                "out_of_stock": products.filter(stock_quantity__lte=0).count(),
            },
            "orders": {
                "total": vendor_orders.count(),
                "by_status": status_counts,
            },
            "revenue": {
                "delivered": float(delivered_revenue),
                "pipeline": float(pipeline_revenue),
            },
            "wallet": {
                "balance": float(wallet.balance),
                "credit_limit": float(wallet.credit_limit),
            },
>>>>>>> d3f86bdf3dac8fc402d56ff1ebace7e1271c6a92
        })

@extend_schema(tags=['Vendors'])
class ShopReviewViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = ShopReview.objects.all()
    serializer_class = ShopReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        shop_id = self.request.query_params.get('shop_id')
        if shop_id:
            return ShopReview.objects.filter(shop_id=shop_id).order_by('-created_at')
        return ShopReview.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
<<<<<<< HEAD
        serializer.save(reviewer=self.request.user)
=======
        shop = serializer.validated_data.get('shop')
        if ShopReview.objects.filter(shop=shop, reviewer=self.request.user).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "You have already reviewed this shop."})
        serializer.save(reviewer=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.reviewer != self.request.user and not is_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only edit your own review.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.reviewer != self.request.user and not is_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only delete your own review.")
        instance.delete()
>>>>>>> d3f86bdf3dac8fc402d56ff1ebace7e1271c6a92

@extend_schema(tags=['Vendors'])
class AdminVendorRatingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Dedicated Admin API for monitoring and adjusting Vendor Ratings.
    """
    queryset = ShopProfile.objects.all().order_by('-average_rating')
    serializer_class = ShopProfileSerializer
    permission_classes = [IsAdminOrSuperAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    
    # Enable filtering by shop type
    filterset_fields = ['shop_type']
    # Enable text search by shop name or phone number
    search_fields = ['shop_name', 'user__phone_number', 'contact_email']

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['patch'])
    def adjust_rating(self, request, pk=None):
        shop = self.get_object()
        adjustment = request.data.get('admin_rating_adjustment')
        
        if adjustment is None:
            return Response({"error": "admin_rating_adjustment is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            adjustment = float(adjustment)
        except ValueError:
            return Response({"error": "Invalid adjustment value. Must be a number."}, status=status.HTTP_400_BAD_REQUEST)
            
        shop.admin_rating_adjustment = adjustment
        # Trigger the recalculation
        
        # Calculate base average from reviews
        reviews = shop.reviews.all()
        total = reviews.count()
        if total > 0:
            avg = sum(r.average_rating for r in reviews) / float(total)
        else:
            avg = 0.0
            
        shop.average_rating = min(max(round(avg + shop.admin_rating_adjustment, 2), 0.0), 5.0)
        shop.save(update_fields=['admin_rating_adjustment', 'average_rating', 'updated_at'])
        
        return Response(self.get_serializer(shop).data)
