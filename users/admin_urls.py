from django.urls import path, re_path, include
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
    re_path(r'^login/?$', AdminLoginView.as_view(), name='admin-login'),
    re_path(r'^permissions/?$', PermissionListView.as_view(), name='admin-permissions'),
    re_path(r'^dashboard/analytics/?$', AdminAnalyticsDashboardAPIView.as_view(), name='admin-analytics'),
    path('', include(router.urls)),
]
