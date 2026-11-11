from django.db.models import Q, F
from rest_framework import viewsets, permissions, exceptions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Category, Product, ProductImage
from vendors.models import ShopProfile
from .serializers import (
    CategorySerializer, CategoryTreeSerializer,
    ProductSerializer, ProductImageSerializer, ProductRejectSerializer
)
from users.permissions import AdminBypassPermission, IsAdminOrSuperAdmin, IsAdminOrReadOnly

def is_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    if hasattr(user, 'role') and user.role and user.role.name == 'ROLE' and user.role.value.upper() == 'ADMIN':
        return True
    return False

@extend_schema(tags=['Products'])
class CategoryViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['parent']
    search_fields = ['name', 'description']

    @extend_schema(
        summary="Get Category Tree (Hierarchical nested tree with pagination)",
        responses={200: CategoryTreeSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='tree')
    def tree(self, request):
        root_categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories').order_by('name')
        
        # Apply search filtering on root categories if provided
        search_query = request.query_params.get('search')
        if search_query:
            root_categories = root_categories.filter(
                Q(name__icontains=search_query) | Q(description__icontains=search_query)
            )

        page = self.paginate_queryset(root_categories)
        if page is not None:
            serializer = CategoryTreeSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = CategoryTreeSerializer(root_categories, many=True, context={'request': request})
        return Response(serializer.data)

@extend_schema(tags=['Products'])
class ProductViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AdminBypassPermission]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['category', 'is_active', 'shop', 'approval_status']
    search_fields = ['title', 'description']

    def get_queryset(self):
        user = self.request.user
        base_qs = Product.objects.select_related('shop', 'category', 'shop__city').prefetch_related('images')
        
        # If Admin, allow viewing all products or filtering by query params
        if is_admin(user):
            qs = base_qs.order_by('-created_at')
            approval_status = self.request.query_params.get('approval_status')
            if approval_status:
                return qs.filter(approval_status=approval_status.upper())
            return qs

        # Public Marketplace (Buyers, Guests, and Vendors browsing the public store):
        # ALWAYS show only active, approved products from unblocked shops
        return base_qs.filter(
            is_active=True, 
            approval_status='APPROVED', 
            shop__is_blocked=False
        ).order_by('-created_at')

    @extend_schema(
        summary="List all products belonging to the logged-in vendor",
        responses={200: ProductSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='my-products', permission_classes=[permissions.IsAuthenticated])
    def my_products(self, request):
        if not hasattr(request.user, 'vendor_shop_profile'):
            return Response({"error": "Only vendors with a shop profile can view their own products."}, status=status.HTTP_403_FORBIDDEN)
        
        queryset = Product.objects.filter(shop=request.user.vendor_shop_profile).order_by('-created_at')
        
        # Optional filter by status for vendor
        status_param = request.query_params.get('approval_status')
        if status_param:
            queryset = queryset.filter(approval_status=status_param.upper())
            
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="List Low Stock Products (Smart Inventory Alert)",
        description="Returns products where stock_quantity <= low_stock_threshold. Admins see all low-stock products; Vendors see their shop's low-stock products.",
        responses={200: ProductSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='low-stock', permission_classes=[permissions.IsAuthenticated])
    def low_stock(self, request):
        user = request.user
        if is_admin(user):
            queryset = Product.objects.filter(stock_quantity__lte=F('low_stock_threshold')).order_by('stock_quantity')
        elif hasattr(user, 'vendor_shop_profile'):
            queryset = Product.objects.filter(shop=user.vendor_shop_profile, stock_quantity__lte=F('low_stock_threshold')).order_by('stock_quantity')
        else:
            return Response({"error": "Only admins and vendors can view low stock alerts."}, status=status.HTTP_403_FORBIDDEN)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        user = self.request.user
        if not user or not user.is_authenticated:
            raise exceptions.NotAuthenticated("Authentication required.")

        if is_admin(user):
            # If Admin or authorized Staff posts, allow selecting a specific shop or fallback
            shop_id = self.request.data.get('shop') or self.request.data.get('shop_id')
            if shop_id:
                shop = ShopProfile.objects.filter(id=shop_id).first()
                if not shop:
                    raise exceptions.ValidationError({"error": f"Shop with id {shop_id} does not exist."})
            elif hasattr(user, 'vendor_shop_profile'):
                shop = user.vendor_shop_profile
            else:
                shop = ShopProfile.objects.first()
                if not shop:
                    raise exceptions.ValidationError({"error": "No shop exists in the system to assign product to."})

            # Products created by Superadmin / Staff / Admin are automatically APPROVED and published directly
            serializer.save(shop=shop, approval_status='APPROVED')
        elif hasattr(user, 'vendor_shop_profile'):
            # If vendor has special auto-approval permission granted by superadmin
            if user.has_perm('products.can_auto_approve_product'):
                serializer.save(shop=user.vendor_shop_profile, approval_status='APPROVED')
            else:
                serializer.save(shop=user.vendor_shop_profile, approval_status='PENDING')
        else:
            raise exceptions.PermissionDenied("Only registered vendors with a shop profile or admins can create products.")

    @extend_schema(
        summary="List pending products awaiting admin approval",
        responses={200: ProductSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrSuperAdmin])
    def pending(self, request):
        products = Product.objects.filter(approval_status='PENDING').order_by('-created_at')
        return Response(ProductSerializer(products, many=True).data)

    @extend_schema(
        summary="Approve product",
        request=None,
        responses={200: OpenApiResponse(description="Product approved successfully")}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrSuperAdmin])
    def approve(self, request, pk=None):
        product = self.get_object()
        product.approval_status = 'APPROVED'
        product.rejection_reason = None
        product.save()
        return Response({"status": "Product approved successfully", "product": ProductSerializer(product).data})

    @extend_schema(
        summary="Reject product",
        request=ProductRejectSerializer,
        responses={200: OpenApiResponse(description="Product rejected successfully")}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrSuperAdmin])
    def reject(self, request, pk=None):
        product = self.get_object()
        serializer = ProductRejectSerializer(data=request.data)
        serializer.is_valid()
        product.approval_status = 'REJECTED'
        product.rejection_reason = serializer.validated_data.get('rejection_reason', '') if serializer.is_valid() else request.data.get('rejection_reason', '')
        product.save()
        return Response({"status": "Product rejected successfully", "product": ProductSerializer(product).data})

@extend_schema(tags=['Products'])
class ProductImageViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    parser_classes = (MultiPartParser, FormParser)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['product']
