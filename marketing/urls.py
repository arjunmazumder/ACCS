from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BannerViewSet, CouponValidateView, CouponViewSet, LandingOrderView, LandingPageViewSet, PublicLandingPageView,
    SiteSettingsView,
)

router = DefaultRouter()
router.register(r'banners', BannerViewSet, basename='banner')
router.register(r'landing-pages', LandingPageViewSet, basename='landing-page')
router.register(r'coupons', CouponViewSet, basename='coupon')

urlpatterns = [
    path('site-settings/', SiteSettingsView.as_view(), name='site-settings'),
    path('coupons/validate/', CouponValidateView.as_view(), name='coupon-validate'),
    path('landing/<slug:slug>/', PublicLandingPageView.as_view(), name='landing-public'),
    path('landing/<slug:slug>/order/', LandingOrderView.as_view(), name='landing-order'),
    path('', include(router.urls)),
]
