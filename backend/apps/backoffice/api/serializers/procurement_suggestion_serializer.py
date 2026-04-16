from rest_framework import serializers


class ProcurementOfferBriefSerializer(serializers.Serializer):
    offer_id = serializers.CharField(allow_null=True)
    supplier_id = serializers.CharField(allow_null=True)
    supplier_code = serializers.CharField()
    supplier_name = serializers.CharField()
    supplier_sku = serializers.CharField()
    purchase_price = serializers.CharField(allow_null=True)
    currency = serializers.CharField()
    stock_qty = serializers.IntegerField()
    lead_time_days = serializers.IntegerField(allow_null=True)
    is_available = serializers.BooleanField()


class ProcurementItemRecommendationSerializer(serializers.Serializer):
    order_item_id = serializers.CharField()
    order_id = serializers.CharField()
    order_number = serializers.CharField(required=False)
    product_id = serializers.CharField()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    quantity = serializers.IntegerField()
    current_procurement_status = serializers.CharField()
    recommended_offer = ProcurementOfferBriefSerializer()
    selected_offer_id = serializers.CharField(allow_null=True)
    can_fulfill = serializers.BooleanField()
    partially_available = serializers.BooleanField()
    fallback_used = serializers.BooleanField()
    availability_status = serializers.CharField(allow_blank=True)
    availability_label = serializers.CharField(allow_blank=True)
    eta_days = serializers.IntegerField(allow_null=True)
    issues = serializers.ListField(child=serializers.CharField())


class ProcurementSupplierGroupSerializer(serializers.Serializer):
    supplier_id = serializers.CharField(allow_null=True)
    supplier_code = serializers.CharField()
    supplier_name = serializers.CharField()
    items = ProcurementItemRecommendationSerializer(many=True)
    items_count = serializers.IntegerField()
    total_quantity = serializers.IntegerField()


class ProcurementSuggestionsSerializer(serializers.Serializer):
    groups = ProcurementSupplierGroupSerializer(many=True)
    groups_count = serializers.IntegerField()
    items_count = serializers.IntegerField()
