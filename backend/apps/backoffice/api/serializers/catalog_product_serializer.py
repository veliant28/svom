from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Brand, Category, Product
from apps.catalog.services import generate_unique_product_slug, sanitize_product_name
from apps.pricing.models import SupplierOffer


class BackofficeCatalogProductSerializer(serializers.ModelSerializer):
    brand = serializers.PrimaryKeyRelatedField(queryset=Brand.objects.all())
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    brand_name = serializers.CharField(source="brand.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    final_price = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    price_updated_at = serializers.SerializerMethodField()
    supplier_price = serializers.SerializerMethodField()
    supplier_currency = serializers.SerializerMethodField()
    applied_markup_percent = serializers.SerializerMethodField()
    applied_markup_policy_name = serializers.SerializerMethodField()
    applied_markup_policy_scope = serializers.SerializerMethodField()
    warehouse_segments = serializers.SerializerMethodField()
    supplier_sku = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "article",
            "name",
            "slug",
            "brand",
            "brand_name",
            "category",
            "category_name",
            "final_price",
            "currency",
            "price_updated_at",
            "supplier_price",
            "supplier_currency",
            "applied_markup_percent",
            "applied_markup_policy_name",
            "applied_markup_policy_scope",
            "warehouse_segments",
            "supplier_sku",
            "short_description",
            "description",
            "is_active",
            "is_featured",
            "is_new",
            "is_bestseller",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "brand_name", "category_name")
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
            "article": {"required": False, "allow_blank": True},
            "short_description": {"required": False, "allow_blank": True},
            "description": {"required": False, "allow_blank": True},
        }

    def validate_name(self, value: str) -> str:
        cleaned = sanitize_product_name(value)
        if not cleaned:
            raise serializers.ValidationError("Название товара обязательно.")
        return cleaned

    def validate_sku(self, value: str) -> str:
        cleaned = sanitize_product_name(value)
        if not cleaned:
            raise serializers.ValidationError("SKU обязателен.")
        return cleaned

    def validate_slug(self, value: str) -> str:
        return (value or "").strip()

    def validate(self, attrs):
        instance: Product | None = getattr(self, "instance", None)
        instance_id = str(instance.id) if instance is not None else None

        if "name" in attrs:
            attrs["name"] = sanitize_product_name(attrs["name"])

        if "article" in attrs:
            attrs["article"] = sanitize_product_name(attrs["article"])

        if "sku" in attrs:
            attrs["sku"] = sanitize_product_name(attrs["sku"])

        name_for_slug = attrs.get("name") or (instance.name if instance is not None else "")
        provided_slug = attrs.get("slug", None)
        if provided_slug is not None:
            attrs["slug"] = generate_unique_product_slug(
                name=name_for_slug,
                preferred_slug=provided_slug,
                exclude_product_id=instance_id,
            )

        return attrs

    def create(self, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = generate_unique_product_slug(name=validated_data["name"])
        return super().create(validated_data)

    @staticmethod
    def _resolve_product_price(obj: Product):
        cached = getattr(obj, "_backoffice_product_price", None)
        if cached is not None:
            return cached

        try:
            product_price = obj.product_price
        except Product.product_price.RelatedObjectDoesNotExist:
            product_price = None
        obj._backoffice_product_price = product_price
        return product_price

    @staticmethod
    def _resolve_supplier_purchase_price(obj: Product) -> tuple[Decimal | None, str | None]:
        prefetched = getattr(obj, "backoffice_supplier_offers", None)
        if prefetched:
            best_offer = prefetched[0]
            if best_offer.purchase_price and best_offer.purchase_price > 0:
                return best_offer.purchase_price, best_offer.currency

        offer = (
            SupplierOffer.objects.filter(product=obj)
            .select_related("supplier")
            .order_by("supplier__priority", "-updated_at", "id")
            .first()
        )
        if offer and offer.purchase_price and offer.purchase_price > 0:
            return offer.purchase_price, offer.currency

        return None, None

    def get_final_price(self, obj: Product):
        product_price = self._resolve_product_price(obj)
        if product_price is None or not product_price.final_price or product_price.final_price <= 0:
            return None
        return f"{product_price.final_price:.2f}"

    def get_currency(self, obj: Product):
        product_price = self._resolve_product_price(obj)
        return product_price.currency if product_price is not None else None

    def get_price_updated_at(self, obj: Product):
        product_price = self._resolve_product_price(obj)
        return product_price.updated_at if product_price is not None else None

    def get_supplier_price(self, obj: Product):
        product_price = self._resolve_product_price(obj)
        if product_price is not None and product_price.purchase_price and product_price.purchase_price > 0:
            return f"{product_price.purchase_price:.2f}"

        supplier_price, _ = self._resolve_supplier_purchase_price(obj)
        if supplier_price is None:
            return None
        return f"{supplier_price:.2f}"

    def get_supplier_currency(self, obj: Product):
        product_price = self._resolve_product_price(obj)
        if product_price is not None and product_price.currency:
            return product_price.currency

        _, supplier_currency = self._resolve_supplier_purchase_price(obj)
        return supplier_currency

    def get_applied_markup_percent(self, obj: Product):
        product_price = self._resolve_product_price(obj)
        if product_price is None or product_price.policy is None:
            return None
        return f"{product_price.policy.percent_markup:.2f}"

    def get_applied_markup_policy_name(self, obj: Product):
        product_price = self._resolve_product_price(obj)
        if product_price is None or product_price.policy is None:
            return ""
        return product_price.policy.name or ""

    def get_applied_markup_policy_scope(self, obj: Product):
        product_price = self._resolve_product_price(obj)
        if product_price is None or product_price.policy is None:
            return ""
        return product_price.policy.scope

    @staticmethod
    def _extract_warehouse_segments(raw_payload: dict, *, source_code: str) -> list[dict]:
        if not isinstance(raw_payload, dict):
            return []

        segments: list[dict] = []
        for key, value in raw_payload.items():
            label = str(key).lower()
            is_warehouse = (
                "склад" in label
                or "warehouse" in label
                or "обл" in label
                or label.startswith("count_warehouse_")
            )
            if not is_warehouse:
                continue

            normalized = str(value or "").strip()
            if not normalized:
                continue

            segments.append(
                {
                    "key": str(key),
                    "value": normalized,
                    "source_code": source_code,
                }
            )
        return segments

    def get_warehouse_segments(self, obj: Product):
        prefetched = getattr(obj, "backoffice_raw_offers", None)
        raw_offers = prefetched
        if raw_offers is None:
            raw_offers = (
                obj.raw_supplier_offers.select_related("source", "supplier")
                .order_by("supplier__priority", "source__code", "-updated_at", "-id")
            )

        collected_by_source: dict[str, list[dict]] = {}
        for raw_offer in raw_offers:
            source_code = str(getattr(raw_offer.source, "code", "") or "").lower()
            if not source_code or source_code in collected_by_source:
                continue

            segments = self._extract_warehouse_segments(raw_offer.raw_payload or {}, source_code=source_code)
            if segments:
                collected_by_source[source_code] = segments

        flattened: list[dict] = []
        for segments in collected_by_source.values():
            flattened.extend(segments)
        return flattened

    def get_supplier_sku(self, obj: Product) -> str:
        prefetched = getattr(obj, "backoffice_supplier_offers", None)
        if prefetched:
            return prefetched[0].supplier_sku

        offer = (
            SupplierOffer.objects.filter(product=obj)
            .order_by("supplier__priority", "-updated_at", "id")
            .first()
        )
        if offer and offer.supplier_sku:
            return offer.supplier_sku
        return obj.sku
