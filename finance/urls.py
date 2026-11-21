from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import FinanceReportView, FinanceSettingsView, LedgerEntryViewSet

router = DefaultRouter()
router.register('ledger', LedgerEntryViewSet, basename='finance-ledger')

urlpatterns = [
    path('reports/', FinanceReportView.as_view(), name='finance-reports'),
    path('settings/', FinanceSettingsView.as_view(), name='finance-settings'),
] + router.urls
