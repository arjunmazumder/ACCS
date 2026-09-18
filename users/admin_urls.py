from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AdminLoginView, PermissionListView, RoleViewSet, StaffViewSet
from vendors.views import AdminVendorRatingViewSet
from core.views import AdminAnalyticsDashboardAPIView, BroadcastAnnouncementViewSet

router = DefaultRouter()
router.register(r'roles', RoleViewSet, basename='admin-roles')
router.register(r'staff', StaffViewSet, basename='admin-staff')
router.register(r'ratings/vendors', AdminVendorRatingViewSet, basename='admin-ratings-vendors')
router.register(r'broadcast', BroadcastAnnouncementViewSet, basename='admin-broadcast')

urlpatterns = [
    path('login/', AdminLoginView.as_view(), name='admin-login'),
    path('permissions/', PermissionListView.as_view(), name='admin-permissions'),
    path('dashboard/analytics/', AdminAnalyticsDashboardAPIView.as_view(), name='admin-analytics'),
    path('', include(router.urls)),
]
