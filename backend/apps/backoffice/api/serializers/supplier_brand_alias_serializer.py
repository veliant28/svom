from rest_framework import serializers

from apps.supplier_imports.models import SupplierBrandAlias


class SupplierBrandAliasSerializer(serializers.ModelSerializer):
    source_code = serializers.CharField(source="source.code", read_only=True)
    supplier_code = serializers.CharField(source="supplier.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    canonical_brand_label = serializers.SerializerMethodField()

    class Meta:
        model = SupplierBrandAlias
        fields = (
            "id",
            "source",
            "source_code",
            "supplier",
            "supplier_code",
            "supplier_name",
            "canonical_brand",
            "canonical_brand_name",
            "canonical_brand_label",
            "supplier_brand_alias",
            "normalized_alias",
            "is_active",
            "priority",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("normalized_alias", "created_at", "updated_at")

    def get_canonical_brand_label(self, obj: SupplierBrandAlias) -> str:
        if obj.canonical_brand:
            return obj.canonical_brand.name
        return obj.canonical_brand_name
