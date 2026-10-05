from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, viewsets, status, filters
from rest_framework.decorators import action
from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema

from users.permissions import IsAdminOrSuperAdmin
from .models import Wallet, WalletTransaction
from .serializers import (
    WalletSerializer, WalletTransactionSerializer,
    UpdateCreditLimitSerializer, AddDiscountSerializer
)

@extend_schema(tags=['Wallets'])
class MyWalletView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WalletSerializer

    def get(self, request):
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        serializer = WalletSerializer(wallet)
        return Response(serializer.data)

@extend_schema(tags=['Wallets'])
class MyWalletTransactionsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WalletTransactionSerializer
    queryset = WalletTransaction.objects.none()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['transaction_type']
    search_fields = ['description']

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return WalletTransaction.objects.none()
        wallet, created = Wallet.objects.get_or_create(user=self.request.user)
        return WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')

@extend_schema(tags=['Wallets'])
class AdminWalletViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wallet.objects.all().order_by('-created_at')
    serializer_class = WalletSerializer
    permission_classes = [IsAdminOrSuperAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['user__phone_number', 'user__full_name', 'user__vendor_shop_profile__shop_name']

    @action(detail=True, methods=['patch'], url_path='update-credit-limit')
    def update_credit_limit(self, request, pk=None):
        wallet = self.get_object()
        serializer = UpdateCreditLimitSerializer(wallet, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(WalletSerializer(wallet).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='add-discount')
    def add_discount(self, request, pk=None):
        wallet = self.get_object()
        serializer = AddDiscountSerializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data['amount']
            description = serializer.validated_data.get('description', 'Admin discount added')
            
            with transaction.atomic():
                wallet.balance += amount
                wallet.save(update_fields=['balance', 'updated_at'])
                
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='DISCOUNT',
                    amount=amount,
                    description=description
                )
                
            return Response(WalletSerializer(wallet).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(tags=['Wallets'], summary="List blocked vendor profiles")
class BlockedProfilesAPIView(generics.ListAPIView):
    serializer_class = WalletSerializer
    permission_classes = [IsAdminOrSuperAdmin]
    permission_model = Wallet
    filter_backends = [filters.SearchFilter]
    search_fields = ['user__phone_number', 'user__full_name', 'user__vendor_shop_profile__shop_name']

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return Wallet.objects.filter(user__vendor_shop_profile__is_blocked=True).distinct().order_by('-created_at')

@extend_schema(tags=['Wallets'])
class AdminWalletTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WalletTransaction.objects.all().order_by('-created_at')
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAdminOrSuperAdmin]
    permission_model = Wallet
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['transaction_type']
    search_fields = ['description', 'wallet__user__phone_number', 'wallet__user__full_name']

