from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from wallets.views import BlockedProfilesAPIView

urlpatterns = [
    # Swagger & OpenAPI Documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui-alias'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    path('blocked-profiles/', BlockedProfilesAPIView.as_view(), name='blocked-profiles'),
    path('admin/', include('users.admin_urls')),
    path('auth/', include('users.urls')),
    path('lookup/', include('lookup.urls')),
    path('core/', include('core.urls')),
    path('vendors/', include('vendors.urls')),
    path('products/', include('products.urls')),
    path('orders/', include('orders.urls')),
    path('wallets/', include('wallets.urls')),
]
