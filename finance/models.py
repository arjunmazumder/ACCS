from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class FinanceSettings(models.Model):
    """Fees the platform pays to third parties, used to work out net amounts in the reports."""
    gateway_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('2.00'),
        help_text='Payment gateway clearance fee, % of each online payment')
    courier_cod_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('1.00'),
        help_text='Courier cash-on-delivery handling fee, % of the cash collected')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Finance settings'
        verbose_name_plural = 'Finance settings'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Finance settings'


class LedgerEntry(models.Model):
    """
    Money that actually moved, recorded by the admin: what came in from the courier and the payment
    gateway, what was paid out to vendors and refunded to customers, and other income/expenses.
    """
    COURIER_REMITTANCE = 'COURIER_REMITTANCE'
    GATEWAY_SETTLEMENT = 'GATEWAY_SETTLEMENT'
    VENDOR_PAYOUT = 'VENDOR_PAYOUT'
    REFUND = 'REFUND'
    OTHER_INCOME = 'OTHER_INCOME'
    EXPENSE = 'EXPENSE'
    KIND_CHOICES = (
        (COURIER_REMITTANCE, 'Received from courier'),
        (GATEWAY_SETTLEMENT, 'Received from payment gateway'),
        (VENDOR_PAYOUT, 'Paid to vendor'),
        (REFUND, 'Refunded to customer'),
        (OTHER_INCOME, 'Other income'),
        (EXPENSE, 'Expense'),
    )
    INCOMING = (COURIER_REMITTANCE, GATEWAY_SETTLEMENT, OTHER_INCOME)

    METHOD_CHOICES = (
        ('CASH', 'Cash'),
        ('BANK', 'Bank transfer'),
        ('BKASH', 'bKash'),
        ('NAGAD', 'Nagad'),
        ('ROCKET', 'Rocket'),
        ('GATEWAY', 'Payment gateway'),
        ('OTHER', 'Other'),
    )

    kind = models.CharField(max_length=30, choices=KIND_CHOICES, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.localdate, db_index=True)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='BANK')
    reference = models.CharField(max_length=120, blank=True, help_text='Transaction ID, invoice or cheque number')
    note = models.TextField(blank=True)
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_entries')
    shop = models.ForeignKey('vendors.ShopProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_entries')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-date', '-id')
        verbose_name_plural = 'Ledger entries'

    @property
    def is_incoming(self):
        return self.kind in self.INCOMING

    def __str__(self):
        return f'{self.get_kind_display()} ৳{self.amount} on {self.date}'
