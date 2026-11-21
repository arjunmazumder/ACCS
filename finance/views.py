from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdminOrSuperAdmin
from .models import FinanceSettings, LedgerEntry
from .reports import build_report, parse_range
from .serializers import FinanceSettingsSerializer, LedgerEntrySerializer


@extend_schema(tags=['Finance & reports'])
class FinanceReportView(APIView):
    """Sales, vendor settlement, courier, payment gateway and refund reports. ?from=YYYY-MM-DD&to=YYYY-MM-DD"""
    permission_classes = [IsAdminOrSuperAdmin]
    permission_model = LedgerEntry

    def get(self, request):
        return Response(build_report(request.query_params))


@extend_schema(tags=['Finance & reports'])
class LedgerEntryViewSet(viewsets.ModelViewSet):
    """Money that actually moved: courier and gateway payouts received, vendor payouts, refunds, expenses."""
    permission_classes = [IsAdminOrSuperAdmin]
    serializer_class = LedgerEntrySerializer
    queryset = LedgerEntry.objects.select_related('order', 'shop', 'created_by')
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get('kind'):
            qs = qs.filter(kind__in=p['kind'].split(','))
        if p.get('shop'):
            qs = qs.filter(shop_id=p['shop'])
        if p.get('order'):
            qs = qs.filter(order_id=p['order'])
        if p.get('from') or p.get('to'):
            start, end = parse_range(p)
            qs = qs.filter(date__gte=start, date__lte=end)
        if p.get('search'):
            s = p['search']
            qs = qs.filter(Q(reference__icontains=s) | Q(note__icontains=s) | Q(order__order_number__icontains=s) | Q(shop__shop_name__icontains=s))
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema(tags=['Finance & reports'])
class FinanceSettingsView(APIView):
    permission_classes = [IsAdminOrSuperAdmin]
    permission_model = FinanceSettings
    serializer_class = FinanceSettingsSerializer

    def get(self, request):
        return Response(FinanceSettingsSerializer(FinanceSettings.load()).data)

    def patch(self, request):
        serializer = FinanceSettingsSerializer(FinanceSettings.load(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
