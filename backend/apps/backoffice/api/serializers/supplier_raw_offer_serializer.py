from rest_framework import serializers

from apps.supplier_imports.models import SupplierRawOffer


class SupplierRawOfferSerializer(serializers.ModelSerializer):
    source_code = serializers.CharField(source="source.code", read_only=True)
    supplier_code = serializers.CharField(source="supplier.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    product_id = serializers.UUIDField(source="matched_product_id", read_only=True, allow_null=True)
    mapped_category_name = serializers.SerializerMethodField(read_only=True)
    mapped_category_path = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SupplierRawOffer
        fields = (
            "id",
            "run",
            "source",
            "source_code",
            "supplier",
            "supplier_code",
            "supplier_name",
            "artifact",
            "row_number",
            "external_sku",
            "article",
            "normalized_article",
            "brand_name",
            "normalized_brand",
            "product_name",
            "currency",
            "price",
            "stock_qty",
            "lead_time_days",
            "matched_product",
            "product_id",
            "match_status",
            "match_reason",
            "match_candidate_product_ids",
            "matching_attempts",
            "last_matched_at",
            "matched_manually_by",
            "matched_manually_at",
            "ignored_at",
            "mapped_category",
            "mapped_category_name",
            "mapped_category_path",
            "category_mapping_status",
            "category_mapping_reason",
            "category_mapping_confidence",
            "category_mapped_at",
            "category_mapped_by",
            "article_normalization_trace",
            "brand_normalization_trace",
            "is_valid",
            "skip_reason",
            "raw_payload",
            "created_at",
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

    def get_mapped_category_name(self, obj: SupplierRawOffer) -> str:
        if obj.mapped_category is None:
            return ""
        return obj.mapped_category.get_localized_name(self._resolve_locale())

    def get_mapped_category_path(self, obj: SupplierRawOffer) -> str:
        if obj.mapped_category is None:
            return ""

        locale = self._resolve_locale()
        names: list[str] = []
        seen: set[str] = set()
        current = obj.mapped_category
        while current is not None and str(current.id) not in seen:
            seen.add(str(current.id))
            names.append(current.get_localized_name(locale))
            if not current.parent_id:
                break
            current = current.parent

        names.reverse()
        return " / ".join(name for name in names if name)
