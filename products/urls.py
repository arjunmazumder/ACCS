from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    ProductViewSet, ProductImageViewSet, ProductReviewViewSet, WishlistView
)

router = DefaultRouter(trailing_slash=False)
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'product-images', ProductImageViewSet, basename='productimage')
router.register(r'reviews', ProductReviewViewSet, basename='product-review')

urlpatterns = [
    path('wishlist', WishlistView.as_view(), name='wishlist'),
    path('', include(router.urls)),
]
