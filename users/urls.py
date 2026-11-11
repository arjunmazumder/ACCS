from django.urls import path, re_path, include
from rest_framework.routers import SimpleRouter
from drf_spectacular.views import SpectacularSwaggerView, SpectacularRedocView
from .views import (
    LoginView, RefreshTokenView, LogoutView, RegisterView, SendOTPView, 
    VerifyOTPView,
    BuyerRegisterView, BuyerRegisterVerifyView,
    KYCProfileView, UserViewSet, ShippingAddressView,
<<<<<<< HEAD
    UserMeView, ForgotPasswordView, ResetPasswordView
=======
    MeView, ChangePasswordView, ForgotPasswordView, ResetPasswordView, LoginOTPView
>>>>>>> d3f86bdf3dac8fc402d56ff1ebace7e1271c6a92
)

router = SimpleRouter(trailing_slash=False)
router.register(r'', UserViewSet, basename='user')

urlpatterns = [
    # Swagger & Documentation for User APIs
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='users-swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='users-redoc'),

    re_path(r'^register/?$', RegisterView.as_view(), name='register'),
    re_path(r'^login/?$', LoginView.as_view(), name='login'),
    re_path(r'^login-otp/?$', SendOTPView.as_view(), name='login-otp'),
    re_path(r'^getRefreshToken/?$', RefreshTokenView.as_view(), name='refresh-token'),
    re_path(r'^logout/?$', LogoutView.as_view(), name='logout'),
    re_path(r'^send-otp/?$', SendOTPView.as_view(), name='send-otp'),
    re_path(r'^verify-otp/?$', VerifyOTPView.as_view(), name='verify-otp'),
    
    # Password Reset
    re_path(r'^forgot-password/?$', ForgotPasswordView.as_view(), name='forgot-password'),
    re_path(r'^reset-password/?$', ResetPasswordView.as_view(), name='reset-password'),

    # Buyer Auth
    re_path(r'^buyer/register/?$', BuyerRegisterView.as_view(), name='buyer-register'),
    re_path(r'^buyer/register-verify/?$', BuyerRegisterVerifyView.as_view(), name='buyer-register-verify'),

    # User Profile & Shipping Address
<<<<<<< HEAD
    re_path(r'^me/?$', UserMeView.as_view(), name='user-me'),
    re_path(r'^profile/?$', KYCProfileView.as_view(), name='user-profile'),
    re_path(r'^shipping-address/?$', ShippingAddressView.as_view(), name='shipping-address'),
=======
    path('login-otp/', LoginOTPView.as_view(), name='login-otp'),
    path('me/', MeView.as_view(), name='me'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('profile/', KYCProfileView.as_view(), name='user-profile'),
    path('shipping-address/', ShippingAddressView.as_view(), name='shipping-address'),
>>>>>>> d3f86bdf3dac8fc402d56ff1ebace7e1271c6a92
    path('', include(router.urls)),
]
