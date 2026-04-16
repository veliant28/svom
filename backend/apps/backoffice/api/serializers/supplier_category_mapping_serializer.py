from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import Category
from apps.supplier_imports.models import SupplierRawOffer


class CategoryMappingCategoryOptionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    breadcrumb = serializers.CharField()
    is_leaf = serializers.BooleanField()


class SupplierRawOfferCategoryMappingUpdateSerializer(serializers.Serializer):
    category_id = serializers.UUIDField()


class SupplierRawOfferCategoryMappingDetailSerializer(serializers.ModelSerializer):
    supplier_code = serializers.CharField(source="supplier.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    matched_product_id = serializers.UUIDField(read_only=True, allow_null=True)
    matched_product_name = serializers.CharField(source="matched_product.name", read_only=True, default="")
    mapped_category = serializers.SerializerMethodField(read_only=True)
    matched_product_category = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SupplierRawOffer
        fields = (
            "id",
            "supplier_code",
            "supplier_name",
            "external_sku",
            "article",
            "brand_name",
            "product_name",
            "match_status",
            "matched_product_id",
            "matched_product_name",
            "matched_product_category",
            "mapped_category",
            "category_mapping_status",
            "category_mapping_reason",
            "category_mapping_confidence",
            "category_mapped_at",
            "category_mapped_by",
            "updated_at",
        )

    def _resolve_locale(self) -> str | None:
        request = self.context.get("request")
        if request is None:
            return None

        locale = (request.query_params.get("locale") or "").strip()
        if locale:
            return locale

        language_code = getattr(request, "LANGUAGE_CODE", "")
        if language_code:
            return str(language_code)

        accept_language = str(request.headers.get("Accept-Language", "")).strip()
        if not accept_language:
            return None
        return accept_language.split(",", 1)[0]

    def _serialize_category(self, category: Category | None) -> dict | None:
        if category is None:
            return None

        locale = self._resolve_locale()
        names: list[str] = []
        seen: set[str] = set()
        current = category
        while current is not None and str(current.id) not in seen:
            seen.add(str(current.id))
            names.append(current.get_localized_name(locale))
            if not current.parent_id:
                break
            current = current.parent
        names.reverse()

        return {
            "id": str(category.id),
            "name": category.get_localized_name(locale),
            "breadcrumb": " / ".join(item for item in names if item),
            "is_leaf": not category.children.filter(is_active=True).exists(),
        }

    def get_mapped_category(self, obj: SupplierRawOffer) -> dict | None:
        return self._serialize_category(obj.mapped_category)

    def get_matched_product_category(self, obj: SupplierRawOffer) -> dict | None:
        if obj.matched_product is None:
            return None
        return self._serialize_category(obj.matched_product.category)
