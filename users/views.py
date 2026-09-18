from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework import filters, viewsets, mixins
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .permissions import IsAdminOrSuperAdmin
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import action
from django.contrib.auth.models import Group, Permission
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse, OpenApiTypes
from .serializers import (
    LoginSerializer, RegisterSerializer, SendOTPSerializer, VerifyOTPSerializer,
    UserSerializer, KYCProfileSerializer,
    UserWithProfileSerializer, BuyerRegisterSerializer, BuyerRegisterVerifySerializer,
    ShippingAddressSerializer, AdminLoginSerializer, PermissionSerializer, RoleSerializer,
    StaffSerializer, StaffCreateSerializer, StaffUpdateSerializer
)
from .services import login_user, refresh_tokens, logout_user
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from .models import User, OTPVerification, KYCProfile, ShippingAddress
from django.conf import settings
from .utils import generate_otp, send_otp_sms, send_password_sms
from lookup.models import Lookup
from lookup.serializers import LookupSerializer
from api.pagination import CustomPagination

def set_auth_cookies(response, access_token, refresh_token):
    response.set_cookie(
        key='access_token',
        value=access_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite='Lax',
        max_age=settings.JWT_ACCESS_EXPIRATION_MINUTES * 60
    )
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite='Lax',
        max_age=settings.JWT_REFRESH_EXPIRATION_DAYS * 24 * 60 * 60
    )

@extend_schema(
    tags=['Authentication'],
    summary="Register a new user / vendor (Default: VENDOR)",
    description="Registers user with phone and password. Role defaults to VENDOR if not provided. Vendors require NID & KYC documents.",
    request=RegisterSerializer,
)
class RegisterView(APIView):
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            otp_code = generate_otp(user.phone_number)
            expires_at = timezone.now() + timedelta(minutes=5)
            
            OTPVerification.objects.update_or_create(
                phone_number=user.phone_number,
                defaults={
                    'otp_code': otp_code,
                    'is_verified': False,
                    'expires_at': expires_at
                }
            )
            
            send_otp_sms(user.phone_number, otp_code)
            
            response_data = {
                "status": "success",
                "message": "Registration successful. OTP sent to phone number.",
                "data": {
                    "user": UserWithProfileSerializer(user).data
                }
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    tags=['Authentication'],
    summary="Login with phone number and password",
    request=LoginSerializer,
)
class LoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            access_token, refresh_token = login_user(user)
            
            response_data = {
                "status": "success",
                "message": "Login successful.",
                "data": {
                    "access_token": access_token,
                    "user": UserWithProfileSerializer(user).data
                }
            }
            
            response = Response(response_data, status=status.HTTP_200_OK)
            set_auth_cookies(response, access_token, refresh_token)
            return response
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    tags=['Authentication'],
    summary="Refresh access token",
    description="Refreshes access token using refresh_token cookie.",
    request=None,
    responses={200: OpenApiResponse(description="Returns fresh access_token and updates refresh_token cookie")}
)
class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response({'detail': 'Refresh token missing.'}, status=status.HTTP_401_UNAUTHORIZED)
            
        access_token, new_refresh_token = refresh_tokens(refresh_token)
        if not access_token:
            return Response({'detail': 'Invalid or expired refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)
            
        response = Response({'access_token': access_token}, status=status.HTTP_200_OK)
        set_auth_cookies(response, access_token, new_refresh_token)
        return response

@extend_schema(
    tags=['Authentication'],
    summary="Logout user",
    description="Revokes refresh token and clears auth cookies.",
    request=None,
    responses={200: OpenApiResponse(description="Successfully logged out and cookies cleared")}
)
class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token')
        if refresh_token:
            logout_user(refresh_token)
            
        response = Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response

@extend_schema(
    tags=['Authentication'],
    summary="Send OTP to phone number",
    request=SendOTPSerializer,
)
class SendOTPView(APIView):
    permission_classes = [AllowAny]
    serializer_class = SendOTPSerializer

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            otp_code = generate_otp(phone_number)
            expires_at = timezone.now() + timedelta(minutes=5)
            
            OTPVerification.objects.update_or_create(
                phone_number=phone_number,
                defaults={
                    'otp_code': otp_code,
                    'is_verified': False,
                    'expires_at': expires_at
                }
            )
            send_otp_sms(phone_number, otp_code)
            return Response({'detail': 'OTP sent successfully.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    tags=['Authentication'],
    summary="Verify OTP code",
    request=VerifyOTPSerializer,
)
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyOTPSerializer

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            otp_code = serializer.validated_data['otp_code']
            
            try:
                otp_record = OTPVerification.objects.get(phone_number=phone_number)
            except OTPVerification.DoesNotExist:
                return Response({'detail': 'OTP record not found. Please request a new OTP.'}, status=status.HTTP_404_NOT_FOUND)
                
            if otp_record.is_expired():
                return Response({'detail': 'OTP has expired.'}, status=status.HTTP_400_BAD_REQUEST)
                
            if otp_record.otp_code != otp_code:
                return Response({'detail': 'Invalid OTP code.'}, status=status.HTTP_400_BAD_REQUEST)
                
            otp_record.is_verified = True
            otp_record.save()
            
            try:
                user = User.objects.get(phone_number=phone_number)
                user.is_phone_verified = True
                user.save()
                
                if user.is_approved:
                    access_token, refresh_token = login_user(user)
                    response_data = {
                        "status": "success",
                        "message": "Phone number verified and login successful.",
                        "data": {
                            "access_token": access_token,
                            "user": UserWithProfileSerializer(user).data
                        }
                    }
                    response = Response(response_data, status=status.HTTP_200_OK)
                    set_auth_cookies(response, access_token, refresh_token)
                    return response
                else:
                    return Response({
                        "status": "success",
                        "message": "Phone number verified successfully. Account is pending admin approval."
                    }, status=status.HTTP_200_OK)
                    
            except User.DoesNotExist:
                return Response({'detail': 'Phone number verified successfully.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    tags=['Authentication'],
    summary="Get current user KYC profile",
)
class KYCProfileView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = KYCProfileSerializer

    @extend_schema(summary="Get current user KYC profile")
    def get(self, request):
        try:
            profile = KYCProfile.objects.get(user=request.user)
            serializer = KYCProfileSerializer(profile)
            return Response(serializer.data)
        except KYCProfile.DoesNotExist:
            return Response({'detail': 'KYC profile not found.'}, status=status.HTTP_404_NOT_FOUND)

@extend_schema(tags=['Admin Management'])
class UserViewSet(mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin,
                  viewsets.GenericViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = User.objects.all()
    permission_classes = [IsAdminOrSuperAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['phone_number', 'full_name']

    def get_queryset(self):
        queryset = User.objects.select_related('role', 'kyc_profile').order_by('-created_at')
        role_id = self.request.query_params.get('role_id')
        kyc_status = self.request.query_params.get('kyc_status')
        if role_id:
            queryset = queryset.filter(role_id=role_id)
        if kyc_status:
            queryset = queryset.filter(kyc_profile__status=kyc_status.upper())
        return queryset

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve', 'pending']:
            return UserWithProfileSerializer
        return UserSerializer

    @extend_schema(summary="List users pending approval or phone verification")
    @action(detail=False, methods=['get'], url_path='pending')
    def pending(self, request):
        queryset = self.filter_queryset(self.get_queryset().filter(Q(is_approved=False) | Q(is_phone_verified=False)))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Approve user KYC & activate account", responses={200: OpenApiResponse(description="User KYC approved")})
    @action(detail=True, methods=['post'], url_path='approve-kyc')
    def approve_kyc(self, request, pk=None):
        user = self.get_object()
        if hasattr(user, 'kyc_profile'):
            user.kyc_profile.status = 'APPROVED'
            user.kyc_profile.verified_at = timezone.now()
            user.kyc_profile.save()
            user.is_approved = True
            user.save()
            return Response({'detail': 'User KYC approved successfully.'}, status=status.HTTP_200_OK)
        return Response({'detail': 'No KYC profile found for this user.'}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Reject user KYC", responses={200: OpenApiResponse(description="User KYC rejected")})
    @action(detail=True, methods=['post'], url_path='reject-kyc')
    def reject_kyc(self, request, pk=None):
        user = self.get_object()
        if hasattr(user, 'kyc_profile'):
            user.kyc_profile.status = 'REJECTED'
            user.kyc_profile.save()
            return Response({'detail': 'User KYC rejected successfully.'}, status=status.HTTP_200_OK)
        return Response({'detail': 'No KYC profile found for this user.'}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Suspend user account", responses={200: OpenApiResponse(description="Account suspended")})
    @action(detail=True, methods=['post'], url_path='suspend')
    def suspend(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({'detail': 'User account suspended successfully.'}, status=status.HTTP_200_OK)

    @extend_schema(summary="Unsuspend/Activate user account", responses={200: OpenApiResponse(description="Account activated")})
    @action(detail=True, methods=['post'], url_path='unsuspend')
    def unsuspend(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save()
        return Response({'detail': 'User account activated successfully.'}, status=status.HTTP_200_OK)

@extend_schema(
    tags=['Authentication'],
    summary="Buyer quick register - Step 1 (Send OTP)",
    request=BuyerRegisterSerializer,
)
class BuyerRegisterView(APIView):
    permission_classes = [AllowAny]
    serializer_class = BuyerRegisterSerializer

    def post(self, request):
        serializer = BuyerRegisterSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            full_name = serializer.validated_data['full_name']
            
            if User.objects.filter(phone_number=phone_number).exists():
                return Response({'error': 'User with this phone number already exists.'}, status=status.HTTP_400_BAD_REQUEST)
                
            otp_code = generate_otp(phone_number)
            expires_at = timezone.now() + timedelta(minutes=5)
            
            OTPVerification.objects.update_or_create(
                phone_number=phone_number,
                defaults={
                    'otp_code': otp_code,
                    'full_name': full_name,
                    'is_verified': False,
                    'expires_at': expires_at
                }
            )
            send_otp_sms(phone_number, otp_code)
            return Response({'message': 'OTP sent successfully.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    tags=['Authentication'],
    summary="Buyer quick register - Step 2 (Verify OTP, auto-creates buyer & password via SMS)",
    request=BuyerRegisterVerifySerializer,
)
class BuyerRegisterVerifyView(APIView):
    permission_classes = [AllowAny]
    serializer_class = BuyerRegisterVerifySerializer

    def post(self, request):
        serializer = BuyerRegisterVerifySerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            otp_code = serializer.validated_data['otp_code']
            
            otp_record = OTPVerification.objects.filter(phone_number=phone_number, otp_code=otp_code).first()
            if not otp_record:
                return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)
            if otp_record.is_expired():
                return Response({'error': 'OTP has expired.'}, status=status.HTTP_400_BAD_REQUEST)
                
            otp_record.is_verified = True
            otp_record.save()
            
            buyer_role = Lookup.objects.filter(name__iexact='ROLE', value__iexact='BUYER').first()
            if not buyer_role:
                buyer_role, _ = Lookup.objects.get_or_create(
                    name='ROLE',
                    value='BUYER',
                    defaults={'is_active': True}
                )
            
            clean_digits = ''.join(filter(str.isdigit, phone_number))
            default_password = clean_digits[-6:] if len(clean_digits) >= 6 else clean_digits

            user, created = User.objects.get_or_create(
                phone_number=phone_number,
                defaults={
                    'full_name': otp_record.full_name,
                    'role': buyer_role,
                    'is_phone_verified': True,
                    'is_approved': True
                }
            )
            user.role = buyer_role
            user.is_phone_verified = True
            user.is_approved = True
            if otp_record.full_name:
                user.full_name = otp_record.full_name
            user.set_password(default_password)
            user.save()

            # Automatically assign default buyer group
            buyer_group, _ = Group.objects.get_or_create(name='buyer')
            user.groups.add(buyer_group)

            send_password_sms(phone_number, default_password)
            
            access_token, refresh_token = login_user(user)
            response_data = {
                "message": "Registration verified and logged in successfully.",
                "data": {
                    "access_token": access_token,
                    "user": UserWithProfileSerializer(user).data
                }
            }
            response = Response(response_data, status=status.HTTP_201_CREATED)
            set_auth_cookies(response, access_token, refresh_token)
            return response
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    tags=['Shipping Address'],
    summary="Manage User Shipping Address",
)
class ShippingAddressView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ShippingAddressSerializer

    @extend_schema(summary="Get current user shipping address")
    def get(self, request):
        try:
            address = request.user.shipping_address
            serializer = ShippingAddressSerializer(address)
            return Response(serializer.data)
        except ShippingAddress.DoesNotExist:
            return Response({"detail": "Shipping address not found."}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(summary="Create shipping address")
    def post(self, request):
        if hasattr(request.user, 'shipping_address'):
            return Response({"detail": "Shipping address already exists. Use PATCH to update."}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ShippingAddressSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Update/Partially update shipping address")
    def patch(self, request):
        try:
            address = request.user.shipping_address
        except ShippingAddress.DoesNotExist:
            return Response({"detail": "Shipping address not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ShippingAddressSerializer(address, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Delete shipping address")
    def delete(self, request):
        try:
            request.user.shipping_address.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ShippingAddress.DoesNotExist:
            return Response({"detail": "Shipping address not found."}, status=status.HTTP_404_NOT_FOUND)

@extend_schema(
    tags=['Admin Management'],
    summary="Admin/Staff login",
    request=AdminLoginSerializer,
)
class AdminLoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = AdminLoginSerializer

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            access_token, refresh_token = login_user(user)
            
            response_data = {
                "status": "success",
                "message": "Admin login successful.",
                "data": {
                    "access_token": access_token,
                    "user": StaffSerializer(user).data
                }
            }
            
            response = Response(response_data, status=status.HTTP_200_OK)
            set_auth_cookies(response, access_token, refresh_token)
            return response
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    tags=['Admin Management'],
    summary="List all permissions",
)
class PermissionListView(ListAPIView):
    permission_classes = [IsAdminOrSuperAdmin]
    queryset = Permission.objects.all().order_by('content_type__app_label', 'codename')
    serializer_class = PermissionSerializer
    pagination_class = None

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

@extend_schema(tags=['Admin Management'])
class RoleViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    permission_classes = [IsAdminOrSuperAdmin]
    queryset = Group.objects.all().order_by('name')
    serializer_class = RoleSerializer
    pagination_class = None

@extend_schema(tags=['Admin Management'])
class StaffViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    permission_classes = [IsAdminOrSuperAdmin]
    
    def get_queryset(self):
        return User.objects.filter(is_staff=True).prefetch_related('groups').order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return StaffCreateSerializer
        if self.action in ['update', 'partial_update']:
            return StaffUpdateSerializer
        return StaffSerializer
