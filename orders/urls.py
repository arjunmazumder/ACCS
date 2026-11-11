from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CartViewSet, OrderViewSet, AdminOrderViewSet, VendorOrderViewSet,
    PathaoCitiesAPIView, PathaoZonesAPIView, PathaoAreasAPIView,
    PathaoStoresAPIView, PathaoCalculatePriceAPIView, PathaoWebhookAPIView,
<<<<<<< HEAD
    AdminDeliverySettingsAPIView
=======
    DeliverySettingsAPIView
>>>>>>> d3f86bdf3dac8fc402d56ff1ebace7e1271c6a92
)

router = DefaultRouter()
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'buyer/orders', OrderViewSet, basename='buyer-orders')
router.register(r'admin/orders', AdminOrderViewSet, basename='admin-orders')
router.register(r'vendor/orders', VendorOrderViewSet, basename='vendor-orders')

urlpatterns = [
    # Delivery Settings
    path('admin/delivery-settings/', AdminDeliverySettingsAPIView.as_view(), name='admin-delivery-settings'),

    # Pathao Courier Endpoints
    path('pathao/cities/', PathaoCitiesAPIView.as_view(), name='pathao-cities'),
    path('pathao/zones/', PathaoZonesAPIView.as_view(), name='pathao-zones'),
    path('pathao/areas/', PathaoAreasAPIView.as_view(), name='pathao-areas'),
    path('pathao/stores/', PathaoStoresAPIView.as_view(), name='pathao-stores'),
    path('pathao/calculate-price/', PathaoCalculatePriceAPIView.as_view(), name='pathao-calculate-price'),
    
    path('admin/delivery-settings/', DeliverySettingsAPIView.as_view(), name='delivery-settings'),

    # Pathao Webhook
    path('webhooks/pathao/', PathaoWebhookAPIView.as_view(), name='pathao-webhook'),

    path('', include(router.urls)),
]
