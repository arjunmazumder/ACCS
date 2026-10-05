from django.urls import path, include
from rest_framework.routers import SimpleRouter
from drf_spectacular.views import SpectacularSwaggerView, SpectacularRedocView
from .views import (
    LoginView, RefreshTokenView, LogoutView, RegisterView, SendOTPView, 
    VerifyOTPView,
    BuyerRegisterView, BuyerRegisterVerifyView,
    KYCProfileView, UserViewSet, ShippingAddressView,
    MeView, ChangePasswordView, ForgotPasswordView, ResetPasswordView, LoginOTPView
)

router = SimpleRouter(trailing_slash=False)
router.register(r'', UserViewSet, basename='user')

urlpatterns = [
    # Swagger & Documentation for User APIs
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='users-swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='users-redoc'),

    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('getRefreshToken/', RefreshTokenView.as_view(), name='refresh-token'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    
    # Buyer Auth
    path('buyer/register/', BuyerRegisterView.as_view(), name='buyer-register'),
    path('buyer/register-verify/', BuyerRegisterVerifyView.as_view(), name='buyer-register-verify'),

    # User Profile & Shipping Address
    path('login-otp/', LoginOTPView.as_view(), name='login-otp'),
    path('me/', MeView.as_view(), name='me'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('profile/', KYCProfileView.as_view(), name='user-profile'),
    path('shipping-address/', ShippingAddressView.as_view(), name='shipping-address'),
    path('', include(router.urls)),
]
