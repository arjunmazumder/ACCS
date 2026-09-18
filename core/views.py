from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.db.models import Sum, F, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse

from users.permissions import IsAdminOrSuperAdmin
from users.models import User
from orders.models import VendorOrder, OrderCommission, Order
from vendors.models import ShopProfile
from products.models import Category, Product
from products.serializers import CategorySerializer

from .models import Policy, AboutUs, BroadcastAnnouncement
from .serializers import (
    PolicySerializer, AboutUsSerializer, BroadcastAnnouncementSerializer
)

@extend_schema(
    tags=['Core'],
    summary="Get all categories",
    responses={200: OpenApiResponse(description="List of all product categories")}
)
class AllCategoriesView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = CategorySerializer

    def get(self, request):
        product_categories = Category.objects.all()
        
        return Response({
            "product_categories": CategorySerializer(product_categories, many=True).data
        })

@extend_schema(tags=['Core'])
class PolicyViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

@extend_schema(tags=['Core'])
class AboutUsViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = AboutUs.objects.all()
    serializer_class = AboutUsSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

# --- Admin Views ---

@extend_schema(tags=['Core'])
class BroadcastAnnouncementViewSet(viewsets.ModelViewSet):
    """
    Dedicated Admin API for creating and managing global announcements.
    """
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = BroadcastAnnouncement.objects.all().order_by('-created_at')
    serializer_class = BroadcastAnnouncementSerializer
    permission_classes = [IsAdminOrSuperAdmin]

@extend_schema(
    tags=['Core'],
    summary="Admin Analytics Dashboard",
    description="Returns aggregated platform statistics: users, vendors, orders, sales trends, and commissions.",
    responses={200: OpenApiResponse(description="Aggregated platform statistics")}
)
class AdminAnalyticsDashboardAPIView(APIView):
    """
    Returns aggregated stats for the Admin Dashboard.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request, *args, **kwargs):
        total_users = User.objects.count()
        total_vendors = ShopProfile.objects.count()

        total_product_orders = VendorOrder.objects.count()

        # Product sales trend
        product_sales_trend = VendorOrder.objects.filter(status='DELIVERED') \
            .annotate(month=TruncMonth('created_at')) \
            .values('month') \
            .annotate(sales_volume=Sum('subtotal_amount')) \
            .order_by('month')

        # Top Vendors (by average rating)
        top_vendors = ShopProfile.objects.order_by('-average_rating', '-total_reviews')[:5]

        # Commission Calculation
        today = timezone.now().date()
        this_month = today.month
        this_year = today.year

        def get_sum(qs):
            res = qs.aggregate(total=Sum('commission_amount'))['total']
            return float(res) if res else 0.0

        total_commission = get_sum(OrderCommission.objects.all())
        daily_commission = get_sum(OrderCommission.objects.filter(created_at__date=today))
        monthly_commission = get_sum(OrderCommission.objects.filter(created_at__year=this_year, created_at__month=this_month))

        # Inventory Summary
        total_products = Product.objects.count()
        low_stock_products = Product.objects.filter(stock_quantity__gt=0, stock_quantity__lte=F('low_stock_threshold')).count()
        out_of_stock_products = Product.objects.filter(stock_quantity__lte=0).count()

        # Courier & Parcel Summary
        in_transit_parcels = Order.objects.filter(
            Q(pathao_order_status__in=['Pickup_Pending', 'In_Transit']) |
            (Q(status='APPROVED') & Q(pathao_consignment_id__isnull=False) & ~Q(pathao_order_status__in=['Delivered', 'Returned', 'Cancelled']))
        ).count()
        delivered_parcels = Order.objects.filter(Q(status='DELIVERED') | Q(pathao_order_status='Delivered')).count()
        returned_parcels = Order.objects.filter(Q(status='RETURNED') | Q(pathao_order_status='Returned')).count()
        cancelled_parcels = Order.objects.filter(Q(status__in=['CANCELLED', 'REJECTED']) | Q(pathao_order_status='Cancelled')).count()
        pending_restock_parcels = Order.objects.filter(
            Q(status__in=['CANCELLED', 'RETURNED', 'REJECTED']) | Q(pathao_order_status__in=['Returned', 'Cancelled']),
            is_restocked=False,
            vendor_orders__isnull=False
        ).distinct().count()
        restocked_parcels = Order.objects.filter(is_restocked=True).count()

        data = {
            "users": {
                "total": total_users,
                "vendors": total_vendors
            },
            "orders": {
                "total_product_orders": total_product_orders
            },
            "sales_trend": {
                "products": list(product_sales_trend)
            },
            "top_vendors": [
                {"id": v.id, "shop_name": v.shop_name, "rating": v.average_rating} for v in top_vendors
            ],
            "commissions": {
                "daily_commission": round(daily_commission, 2),
                "monthly_commission": round(monthly_commission, 2),
                "total_commission": round(total_commission, 2)
            },
            "inventory_summary": {
                "total_products": total_products,
                "low_stock_products": low_stock_products,
                "out_of_stock_products": out_of_stock_products
            },
            "courier_summary": {
                "in_transit_parcels": in_transit_parcels,
                "delivered_parcels": delivered_parcels,
                "returned_parcels": returned_parcels,
                "cancelled_parcels": cancelled_parcels,
                "pending_restock_parcels": pending_restock_parcels,
                "restocked_parcels": restocked_parcels
            }
        }
        
        return Response(data)
