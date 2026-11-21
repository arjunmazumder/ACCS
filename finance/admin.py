from django.contrib import admin

from .models import FinanceSettings, LedgerEntry


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'kind', 'amount', 'method', 'reference', 'order', 'shop')
    list_filter = ('kind', 'method')
    search_fields = ('reference', 'note', 'order__order_number', 'shop__shop_name')


admin.site.register(FinanceSettings)
