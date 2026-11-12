from django.db.models import Q, F
from rest_framework import viewsets, permissions, exceptions, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Category, Product, ProductImage, ProductReview, WishlistItem
from vendors.models import ShopProfile
from .serializers import (
    CategorySerializer, CategoryTreeSerializer,
    ProductSerializer, ProductImageSerializer, ProductRejectSerializer, ProductReviewSerializer
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

class IsProductOwnerOrReadOnly(AdminBypassPermission):
    """
    Anyone can read. Writes require a vendor with a shop profile (or admin).
    Object-level writes are limited to the product's own shop owner.
    """
    def has_custom_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_custom_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        product = obj.product if isinstance(obj, ProductImage) else obj
        return bool(product.shop and product.shop.user_id == request.user.id)


@extend_schema(tags=['Products'])
class CategoryViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    pagination_class = None
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['parent']
    search_fields = ['name', 'description']

    @extend_schema(
        summary="Get Category Tree (Hierarchical nested tree with pagination)",
        responses={200: CategoryTreeSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='tree')
    def tree(self, request):
        root_categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories').order_by('position', 'name')
        
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
    permission_classes = [IsProductOwnerOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'shop', 'approval_status']
    search_fields = ['title', 'author', 'publisher', 'description', 'shop__shop_name', 'category__name']
    ordering_fields = ['price', 'created_at', 'title', 'stock_quantity']

    @staticmethod
    def _csv(value):
        return [v.strip() for v in str(value or '').split(',') if v.strip()]

    def _apply_filters(self, queryset, skip=()):
        """
        Storefront filters. Multi-value params are comma separated:
        ?category=1,2 (a parent category also matches its sub-categories)
        &publisher=A,B &author=X &min_price= &max_price= &in_stock=1
        `skip` leaves out filters (used to compute facet counts).
        """
        params = self.request.query_params

        categories = [c for c in self._csv(params.get('category')) if c.isdigit()]
        if categories and 'category' not in skip:
            queryset = queryset.filter(Q(category_id__in=categories) | Q(category__parent_id__in=categories))

        for field in ('publisher', 'author'):
            values = self._csv(params.get(field))
            if values and field not in skip:
                queryset = queryset.filter(**{f'{field}__in': values})

        try:
            if params.get('min_price'):
                queryset = queryset.filter(price__gte=float(params['min_price']))
            if params.get('max_price'):
                queryset = queryset.filter(price__lte=float(params['max_price']))
        except ValueError:
            pass

        if params.get('in_stock') in ('1', 'true', 'True'):
            queryset = queryset.filter(stock_quantity__gt=0)

        if params.get('discounted') in ('1', 'true', 'True'):
            from django.utils import timezone
            queryset = (queryset.exclude(discount_type='NONE').filter(discount_value__gt=0)
                        .filter(Q(discount_end_date__isnull=True) | Q(discount_end_date__gte=timezone.now())))
        return queryset

    def filter_queryset(self, queryset):
        return self._apply_filters(super().filter_queryset(queryset))

    @extend_schema(summary="Filter options with counts (categories, publishers, authors) for the current search")
    @action(detail=False, methods=['get'], url_path='facets', permission_classes=[permissions.AllowAny])
    def facets(self, request):
        from django.db.models import Count
        # Search only; every facet ignores its own selection so users can pick several values
        searched = SearchFilter().filter_queryset(request, self.public_queryset(), self)

        def counts(field, skip):
            rows = (self._apply_filters(searched, skip={skip}).exclude(**{f'{field}__isnull': True})
                    .exclude(**{field: ''}).values(field).annotate(count=Count('id')).order_by('-count', field))
            return [{'value': r[field], 'count': r['count']} for r in rows]

        category_rows = (self._apply_filters(searched, skip={'category'})
                         .exclude(category__isnull=True).values('category').annotate(count=Count('id')))
        category_counts = {}
        for row in category_rows:
            category_counts[row['category']] = category_counts.get(row['category'], 0) + row['count']
        for cat in Category.objects.filter(id__in=category_counts.keys(), parent__isnull=False).values('id', 'parent_id'):
            category_counts[cat['parent_id']] = category_counts.get(cat['parent_id'], 0) + category_counts[cat['id']]

        return Response({
            'categories': [{'id': k, 'count': v} for k, v in category_counts.items()],
            'publishers': counts('publisher', 'publisher'),
            'authors': counts('author', 'author'),
        })

    @extend_schema(summary="Home page rows: every top-level category with its latest products")
    @action(detail=False, methods=['get'], url_path='home-sections', permission_classes=[permissions.AllowAny])
    def home_sections(self, request):
        try:
            limit = min(max(int(request.query_params.get('limit', 5)), 1), 20)
        except ValueError:
            limit = 5
        public = self.public_queryset()
        sections = []
        for category in Category.objects.filter(parent__isnull=True).order_by('position', 'name'):
            products = public.filter(Q(category=category) | Q(category__parent=category))
            total = products.count()
            if not total:
                continue
            sections.append({
                'category': {'id': category.id, 'name': category.name, 'description': category.description},
                'total': total,
                'products': ProductSerializer(products[:limit], many=True, context={'request': request}).data,
            })
        return Response(sections)

    def public_queryset(self):
        """What every shopper sees: active, approved products from unblocked shops."""
        return (Product.objects.select_related('shop', 'category', 'shop__city').prefetch_related('images')
                .filter(is_active=True, approval_status='APPROVED', shop__is_blocked=False).order_by('-created_at'))

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
        public_q = Q(is_active=True, approval_status='APPROVED', shop__is_blocked=False)

        # Vendors can also open / edit / delete their own products regardless of approval state
        if self.action in ('retrieve', 'update', 'partial_update', 'destroy') and user and user.is_authenticated and hasattr(user, 'vendor_shop_profile'):
            return base_qs.filter(public_q | Q(shop=user.vendor_shop_profile)).order_by('-created_at')

        return base_qs.filter(public_q).order_by('-created_at')

    @extend_schema(
        summary="List all products belonging to the logged-in vendor",
        responses={200: ProductSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='my-products', permission_classes=[permissions.IsAuthenticated])
    def my_products(self, request):
        if not hasattr(request.user, 'vendor_shop_profile'):
            return Response({"error": "Only vendors with a shop profile can view their own products."}, status=status.HTTP_403_FORBIDDEN)
        
        queryset = self.filter_queryset(
            Product.objects.filter(shop=request.user.vendor_shop_profile)
            .select_related('shop', 'category').prefetch_related('images').order_by('-created_at')
        )
            
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

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance
        if not is_admin(user) and instance.approval_status == 'REJECTED':
            # A corrected product goes back into the admin review queue
            serializer.save(approval_status='PENDING', rejection_reason=None)
        else:
            serializer.save()

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
    permission_classes = [IsProductOwnerOrReadOnly]
    parser_classes = (MultiPartParser, FormParser)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['product']

    def perform_create(self, serializer):
        product = serializer.validated_data.get('product')
        if not is_admin(self.request.user):
            if not product or not product.shop or product.shop.user_id != self.request.user.id:
                raise exceptions.PermissionDenied("You can only add images to your own products.")
        image = serializer.save()
        if image.is_primary:
            ProductImage.objects.filter(product=image.product).exclude(id=image.id).update(is_primary=False)

    def perform_update(self, serializer):
        image = serializer.save()
        if image.is_primary:
            ProductImage.objects.filter(product=image.product).exclude(id=image.id).update(is_primary=False)


def _has_bought(user, product_id):
    from orders.models import OrderItem
    return OrderItem.objects.filter(
        order__buyer=user, product_id=product_id, order__status__in=['APPROVED', 'DELIVERED'],
    ).exists()


@extend_schema(tags=['Products'])
class WishlistView(APIView):
    """The shopper's saved books. GET lists them, POST {product_id} adds, DELETE ?product_id= removes."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = (WishlistItem.objects.filter(user=request.user)
                 .select_related('product__shop', 'product__category').prefetch_related('product__images'))
        products = [i.product for i in items]
        return Response({
            'ids': [p.id for p in products],
            'products': ProductSerializer(products, many=True, context={'request': request}).data,
        })

    def post(self, request):
        product = get_object_or_404(Product, id=request.data.get('product_id'))
        WishlistItem.objects.get_or_create(user=request.user, product=product)
        return Response({'detail': 'Saved to your wishlist.'}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        WishlistItem.objects.filter(user=request.user, product_id=request.query_params.get('product_id')).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=['Products'])
class ProductReviewViewSet(viewsets.ModelViewSet):
    """Book reviews. Anyone can read; buyers who received the book can write one review each."""
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    serializer_class = ProductReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['product']

    def get_queryset(self):
        return ProductReview.objects.select_related('user').order_by('-created_at')

    def perform_create(self, serializer):
        product = serializer.validated_data['product']
        user = self.request.user
        if ProductReview.objects.filter(product=product, user=user).exists():
            raise exceptions.ValidationError({'detail': 'You have already reviewed this book.'})
        if not is_admin(user) and not _has_bought(user, product.id):
            raise exceptions.PermissionDenied('Only buyers who ordered this book can review it.')
        serializer.save(user=user)

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user and not is_admin(self.request.user):
            raise exceptions.PermissionDenied('You can only edit your own review.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user and not is_admin(self.request.user):
            raise exceptions.PermissionDenied('You can only delete your own review.')
        instance.delete()

    @extend_schema(summary='Can the current user review this product?')
    @action(detail=False, methods=['get'], url_path='eligibility', permission_classes=[permissions.AllowAny])
    def eligibility(self, request):
        product_id = request.query_params.get('product')
        user = request.user
        if not user.is_authenticated:
            return Response({'can_review': False, 'reason': 'login'})
        if ProductReview.objects.filter(product_id=product_id, user=user).exists():
            return Response({'can_review': False, 'reason': 'already_reviewed'})
        if not is_admin(user) and not _has_bought(user, product_id):
            return Response({'can_review': False, 'reason': 'not_purchased'})
        return Response({'can_review': True, 'reason': None})
