from rest_framework import serializers

from .models import FinanceSettings, LedgerEntry


class LedgerEntrySerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source='get_kind_display', read_only=True)
    method_label = serializers.CharField(source='get_method_display', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True, default=None)
    shop_name = serializers.CharField(source='shop.shop_name', read_only=True, default=None)
    created_by_name = serializers.SerializerMethodField()
    is_incoming = serializers.BooleanField(read_only=True)

    class Meta:
        model = LedgerEntry
        fields = ('id', 'kind', 'kind_label', 'amount', 'date', 'method', 'method_label', 'reference', 'note',
                  'order', 'order_number', 'shop', 'shop_name', 'is_incoming', 'created_by_name', 'created_at')
        read_only_fields = ('created_at',)

    def get_created_by_name(self, obj):
        u = obj.created_by
        return (u.full_name or u.phone_number) if u else None

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Amount must be more than zero.')
        return value

    def validate(self, data):
        kind = data.get('kind', getattr(self.instance, 'kind', None))
        if kind == LedgerEntry.VENDOR_PAYOUT and not data.get('shop', getattr(self.instance, 'shop', None)):
            raise serializers.ValidationError({'shop': 'Choose the shop that was paid.'})
        if kind == LedgerEntry.REFUND and not data.get('order', getattr(self.instance, 'order', None)):
            raise serializers.ValidationError({'order': 'Choose the order that was refunded.'})
        return data


class FinanceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceSettings
        fields = ('gateway_fee_percent', 'courier_cod_fee_percent', 'updated_at')
        read_only_fields = ('updated_at',)

    def validate(self, data):
        for key, value in data.items():
            if value < 0 or value > 100:
                raise serializers.ValidationError({key: 'Enter a percentage between 0 and 100.'})
        return data
