from __future__ import annotations

from decimal import Decimal
from hashlib import sha1
import re

from rest_framework import serializers

from apps.autodb.selectors.admin_supplier_brands import get_admin_supplier_brand_name_by_id
from apps.backoffice.services import ProductOperationsService
from apps.catalog.models import AutoDbProductLinkQuality, Category, Product, ProductAttribute
from apps.catalog.services import (
    ensure_product_svom_sku,
    generate_unique_product_slug,
    get_product_display_brand_payload,
    get_product_display_name_with_meta,
    get_product_display_sku,
    get_product_internal_import_key,
    is_code_like_product_name,
    is_gpl_product,
    resolve_locale,
    sanitize_product_name,
)
from apps.compatibility.models import ProductFitment
from apps.catalog.services.product_stock import get_available_supplier_offer_stock_sum, resolve_display_stock_qty
from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.gpl_parser import extract_gpl_price_levels


class BackofficeCatalogProductSerializer(serializers.ModelSerializer):
    UTR_WAREHOUSE_COLUMNS: tuple[str, ...] = (
        "Миколаївська обл.",
        "Одеська обл.",
        "Запорізька обл.",
        "Київська обл.",
        "Херсонська обл.",
        "Харківська обл.",
        "КИЇВ-2",
        "Дніпровська обл.",
        "Львівська обл.",
        "Черкаська обл.",
        "Хмельницька обл.",
        "Рівненська обл.",
        "Вінницька обл.",
        "Житомирська обл.",
        "Івано-Франківська обл.",
    )

    brand = serializers.IntegerField(source="brand_id", read_only=True)
    autodb_supplier_id = serializers.IntegerField(required=False, allow_null=True)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_assignable=True), allow_null=True, required=False)
    brand_name = serializers.SerializerMethodField(read_only=True)
    current_brand_name = serializers.SerializerMethodField(read_only=True)
    display_brand = serializers.SerializerMethodField(read_only=True)
    brand_source = serializers.SerializerMethodField(read_only=True)
    autodb_supplier_name = serializers.CharField(read_only=True)
    category_name = serializers.SerializerMethodField(read_only=True)
    final_price = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    price_updated_at = serializers.SerializerMethodField()
    supplier_price = serializers.SerializerMethodField()
    supplier_currency = serializers.SerializerMethodField()
    supplier_price_levels = serializers.SerializerMethodField()
    applied_markup_percent = serializers.SerializerMethodField()
    applied_markup_policy_name = serializers.SerializerMethodField()
    applied_markup_policy_scope = serializers.SerializerMethodField()
    warehouse_segments = serializers.SerializerMethodField()
    supplier_sku = serializers.SerializerMethodField()
    internal_import_key = serializers.SerializerMethodField(read_only=True)
    supplier_offer_seen_at = serializers.SerializerMethodField()
    selected_offer_supplier_code = serializers.SerializerMethodField()
    selected_offer_supplier_sku = serializers.SerializerMethodField()
    selected_offer_purchase_price = serializers.SerializerMethodField()
    selected_offer_stock_qty = serializers.SerializerMethodField()
    selected_offer_raw_article = serializers.SerializerMethodField()
    selected_offer_raw_brand = serializers.SerializerMethodField()
    stock_qty = serializers.SerializerMethodField()
    supplier_offer_stock_sum = serializers.SerializerMethodField()
    supplier_code = serializers.SerializerMethodField()
    supplier_codes = serializers.SerializerMethodField()
    primary_supplier_code = serializers.SerializerMethodField()
    has_product_price = serializers.SerializerMethodField()
    has_available_offer = serializers.SerializerMethodField()
    productprice_status = serializers.SerializerMethodField()
    productprice_status_reason = serializers.SerializerMethodField()
    product_is_active = serializers.BooleanField(source="is_active", read_only=True)
    is_public = serializers.SerializerMethodField()
    published_at = serializers.DateTimeField(read_only=True)
    autodb_link_status = serializers.SerializerMethodField()
    compatibility_available = serializers.SerializerMethodField()
    warehouse_summary = serializers.SerializerMethodField()
    price_tooltip_summary = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    display_name_source = serializers.SerializerMethodField()
    name_quality_flags = serializers.SerializerMethodField()
    raw_supplier_name = serializers.SerializerMethodField()
    raw_supplier_brand = serializers.SerializerMethodField()
    autodb_link_quality_status = serializers.SerializerMethodField(read_only=True)
    autodb_attributes_count = serializers.SerializerMethodField(read_only=True)
    autodb_fitments_count = serializers.SerializerMethodField(read_only=True)
    is_autodb_compatible_data_available = serializers.SerializerMethodField(read_only=True)
    product_display_sku = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "svom_sku",
            "product_display_sku",
            "internal_import_key",
            "article",
            "name",
            "display_name",
            "display_name_source",
            "name_uk",
            "name_ru",
            "name_en",
            "slug",
            "brand",
            "brand_name",
            "current_brand_name",
            "display_brand",
            "brand_source",
            "category",
            "category_name",
            "catalog_source",
            "name_source",
            "name_translation_status",
            "name_manually_locked",
            "autodb_article_key",
            "autodb_supplier_id",
            "autodb_supplier_name",
            "name_quality_flags",
            "raw_supplier_name",
            "raw_supplier_brand",
            "autodb_link_quality_status",
            "autodb_attributes_count",
            "autodb_fitments_count",
            "is_autodb_compatible_data_available",
            "final_price",
            "currency",
            "price_updated_at",
            "supplier_price",
            "supplier_currency",
            "supplier_price_levels",
            "applied_markup_percent",
            "applied_markup_policy_name",
            "applied_markup_policy_scope",
            "warehouse_segments",
            "supplier_sku",
            "supplier_offer_seen_at",
            "selected_offer_supplier_code",
            "selected_offer_supplier_sku",
            "selected_offer_purchase_price",
            "selected_offer_stock_qty",
            "selected_offer_raw_article",
            "selected_offer_raw_brand",
            "stock_qty",
            "supplier_offer_stock_sum",
            "supplier_code",
            "supplier_codes",
            "primary_supplier_code",
            "has_product_price",
            "has_available_offer",
            "productprice_status",
            "productprice_status_reason",
            "product_is_active",
            "is_public",
            "published_at",
            "autodb_link_status",
            "compatibility_available",
            "warehouse_summary",
            "price_tooltip_summary",
            "short_description",
            "description",
            "is_active",
            "is_featured",
            "is_new",
            "is_bestseller",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "brand_name",
            "current_brand_name",
            "display_brand",
            "brand_source",
            "category_name",
            "display_name",
            "display_name_source",
            "internal_import_key",
            "svom_sku",
            "product_display_sku",
            "name_uk",
            "name_ru",
            "name_en",
            "autodb_article_key",
            "autodb_supplier_name",
            "name_quality_flags",
            "raw_supplier_name",
            "raw_supplier_brand",
        )
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
            normalized_sku = sanitize_product_name(attrs["sku"])
            if instance is not None and self._should_preserve_gpl_internal_key(instance=instance):
                attrs["sku"] = instance.sku
            else:
                attrs["sku"] = normalized_sku

        name_for_slug = attrs.get("name") or (instance.name if instance is not None else "")
        provided_slug = attrs.get("slug", None)
        if provided_slug is not None:
            attrs["slug"] = generate_unique_product_slug(
                name=name_for_slug,
                preferred_slug=provided_slug,
                exclude_product_id=instance_id,
            )

        resolved_supplier_id = attrs.get("autodb_supplier_id", getattr(instance, "autodb_supplier_id", None))
        if resolved_supplier_id in ("", None):
            raise serializers.ValidationError({"autodb_supplier_id": "Auto_DB_Pro supplier is required."})

        supplier_id = int(resolved_supplier_id)
        supplier_name = get_admin_supplier_brand_name_by_id(supplier_id)
        if not supplier_name:
            raise serializers.ValidationError({"autodb_supplier_id": "Supplier missing in local Auto_DB_Pro."})

        attrs["brand_id"] = 1
        attrs["autodb_supplier_id"] = supplier_id
        attrs["autodb_supplier_name"] = supplier_name
        attrs["display_brand_name"] = supplier_name
        attrs["brand_source"] = Product.BRAND_SOURCE_AUTODB_PRO
        attrs["brand_source_hash"] = sha1(
            f"{supplier_id}:{Product.BRAND_SOURCE_AUTODB_PRO}:{supplier_name}".encode("utf-8")
        ).hexdigest()

        return attrs

    def _should_preserve_gpl_internal_key(self, *, instance: Product) -> bool:
        internal_key = str(getattr(instance, "sku", "") or "").strip()
        if not internal_key.upper().startswith("GPL-"):
            return False
        return is_gpl_product(instance)

    def get_category_name(self, obj: Product) -> str:
        category = getattr(obj, "category", None)
        if category is None:
            return ""
        return str(category.name or "")

    def _brand_payload(self, obj: Product):
        return get_product_display_brand_payload(obj)

    def get_brand_name(self, obj: Product) -> str:
        return self._brand_payload(obj).display_brand

    def get_display_brand(self, obj: Product) -> str:
        return self._brand_payload(obj).display_brand

    def get_brand_source(self, obj: Product) -> str:
        return self._brand_payload(obj).brand_source

    def get_current_brand_name(self, obj: Product) -> str:
        return sanitize_product_name(str(obj.autodb_supplier_name or obj.display_brand_name or ""))

    def get_internal_import_key(self, obj: Product) -> str:
        return get_product_internal_import_key(obj)

    def get_product_display_sku(self, obj: Product) -> str:
        return get_product_display_sku(obj)

    def create(self, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = generate_unique_product_slug(name=validated_data["name"])
        product = super().create(validated_data)
        ensure_product_svom_sku(product)
        return product

    def update(self, instance, validated_data):
        previous_category_id = str(instance.category_id) if instance.category_id else ""
        updated_product = super().update(instance, validated_data)
        next_category_id = str(updated_product.category_id) if updated_product.category_id else ""
        if previous_category_id and next_category_id and previous_category_id != next_category_id:
            request = self.context.get("request")
            actor = getattr(request, "user", None) if request is not None else None
            ProductOperationsService().bulk_move_to_category(
                product_ids=[str(updated_product.id)],
                category=updated_product.category,
                actor=actor,
                update_import_rules=True,
            )
        return updated_product

    def _resolve_locale(self) -> str:
        request = self.context.get("request")
        if request is None:
            return "uk"

        params = getattr(request, "query_params", None)
        if params is None:
            params = getattr(request, "GET", {})
        explicit = str(params.get("locale") or "").strip()
        if explicit:
            return resolve_locale(explicit)
        return resolve_locale(getattr(request, "LANGUAGE_CODE", "") or "")

    def _resolve_display_name_payload(self, obj: Product) -> tuple[str, str]:
        return get_product_display_name_with_meta(
            obj,
            self._resolve_locale(),
            unknown_label="Товар без названия",
        )

    def get_display_name(self, obj: Product) -> str:
        display_name, _ = self._resolve_display_name_payload(obj)
        return display_name

    def get_display_name_source(self, obj: Product) -> str:
        _, source = self._resolve_display_name_payload(obj)
        return source

    def get_name_quality_flags(self, obj: Product) -> list[str]:
        flags: list[str] = []
        display_name = self.get_display_name(obj)
        if not sanitize_product_name(display_name):
            flags.append("needs_name_enrichment")
        if is_code_like_product_name(str(obj.name or "")):
            flags.append("code_like_name")
        if str(obj.name_source or "") == Product.NAME_SOURCE_SUPPLIER_FALLBACK:
            flags.append("supplier_fallback")
        if not obj.autodb_supplier_id or not str(obj.autodb_article_number or "").strip():
            flags.append("missing_autodb_link")
        if str(obj.name_translation_status or "") in {Product.NAME_TRANSLATION_PENDING, Product.NAME_TRANSLATION_FAILED, ""}:
            flags.append("translation_pending")
        return flags

    def get_raw_supplier_name(self, obj: Product) -> str:
        prefetched = getattr(obj, "backoffice_raw_offers", None)
        if prefetched is not None:
            if not prefetched:
                return ""
            return sanitize_product_name(str(getattr(prefetched[0], "product_name", "") or ""))

        rows = obj.raw_supplier_offers.order_by("-updated_at", "-id").values_list("product_name", flat=True)[:1]
        if not rows:
            return ""
        return sanitize_product_name(str(rows[0] or ""))

    def get_raw_supplier_brand(self, obj: Product) -> str:
        prefetched = getattr(obj, "backoffice_raw_offers", None)
        if prefetched is not None:
            if not prefetched:
                return ""
            return sanitize_product_name(str(getattr(prefetched[0], "brand_name", "") or ""))

        rows = obj.raw_supplier_offers.order_by("-updated_at", "-id").values_list("brand_name", flat=True)[:1]
        if not rows:
            return ""
        return sanitize_product_name(str(rows[0] or ""))

    def to_representation(self, instance):
        payload = super().to_representation(instance)
        payload["sku"] = get_product_display_sku(instance)
        payload["internal_import_key"] = get_product_internal_import_key(instance)
        payload["name"] = payload.get("display_name") or payload.get("name") or ""
        return payload

    def _get_link_quality_status(self, obj: Product) -> str:
        annotated_status = getattr(obj, "_autodb_link_quality_status", None)
        if annotated_status is not None:
            return str(annotated_status or "")
        article_key = str(getattr(obj, "autodb_article_key", "") or "").strip()
        if not article_key:
            return ""
        status = (
            AutoDbProductLinkQuality.objects.filter(product=obj, autodb_article_key=article_key)
            .order_by("-checked_at", "-updated_at")
            .values_list("status", flat=True)
            .first()
        )
        return str(status or "")

    def get_autodb_link_quality_status(self, obj: Product) -> str:
        return self._get_link_quality_status(obj)

    def get_autodb_attributes_count(self, obj: Product) -> int:
        annotated_count = getattr(obj, "_autodb_attributes_count", None)
        if annotated_count is not None:
            return int(annotated_count or 0)
        return ProductAttribute.objects.filter(
            product=obj,
            source=ProductAttribute.SOURCE_AUTODB_PRO,
        ).count()

    def get_autodb_fitments_count(self, obj: Product) -> int:
        annotated_count = getattr(obj, "_autodb_fitments_count", None)
        if annotated_count is not None:
            return int(annotated_count or 0)
        return ProductFitment.objects.filter(
            product=obj,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            is_stale=False,
            excluded_from_public_filtering=False,
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
        ).count()

    def get_is_autodb_compatible_data_available(self, obj: Product) -> bool:
        if self._get_link_quality_status(obj) != AutoDbProductLinkQuality.STATUS_TRUSTED:
            return False
        return self.get_autodb_fitments_count(obj) > 0 or self.get_autodb_attributes_count(obj) > 0

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
    def _resolve_supplier_offer(obj: Product) -> SupplierOffer | None:
        offers = BackofficeCatalogProductSerializer._resolve_supplier_offers(obj)
        if offers:
            return offers[0]

        return (
            SupplierOffer.objects.filter(product=obj)
            .select_related("supplier")
            .order_by("supplier__priority", "-updated_at", "id")
            .first()
        )

    @staticmethod
    def _as_decimal(value: Decimal | int | str | None) -> Decimal:
        if value in (None, ""):
            return Decimal("0")
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    @classmethod
    def _offer_matches_product_price(cls, *, offer: SupplierOffer, product_price) -> bool:
        if product_price is None:
            return False
        return (
            str(offer.currency or "") == str(product_price.currency or "")
            and cls._as_decimal(offer.purchase_price) == cls._as_decimal(product_price.purchase_price)
            and cls._as_decimal(offer.logistics_cost) == cls._as_decimal(product_price.logistics_cost)
            and cls._as_decimal(offer.extra_cost) == cls._as_decimal(product_price.extra_cost)
        )

    @classmethod
    def _resolve_selected_offer(cls, obj: Product) -> SupplierOffer | None:
        cached = getattr(obj, "_backoffice_selected_offer", None)
        if cached is not None:
            return cached

        offers = cls._resolve_supplier_offers(obj)
        product_price = cls._resolve_product_price(obj)
        selected: SupplierOffer | None = None

        if product_price is not None and cls._as_decimal(product_price.purchase_price) > 0:
            matched = [offer for offer in offers if cls._offer_matches_product_price(offer=offer, product_price=product_price)]
            if matched:
                selected = next((offer for offer in matched if offer.is_available), matched[0])

        if selected is None:
            selected = cls._resolve_supplier_offer(obj)

        obj._backoffice_selected_offer = selected
        return selected

    @staticmethod
    def _normalize_compact(value: str | None) -> str:
        return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())

    @classmethod
    def _resolve_selected_raw_offer(cls, obj: Product) -> SupplierRawOffer | None:
        cached = getattr(obj, "_backoffice_selected_raw_offer", None)
        if cached is not None:
            return cached

        selected_offer = cls._resolve_selected_offer(obj)
        if selected_offer is None:
            obj._backoffice_selected_raw_offer = None
            return None

        offer_sku = str(getattr(selected_offer, "supplier_sku", "") or "").strip()
        offer_sku_compact = cls._normalize_compact(offer_sku)
        raw_offers = getattr(obj, "backoffice_raw_offers", None)
        if raw_offers is None:
            raw_offers = list(
                obj.raw_supplier_offers.select_related("source", "supplier").order_by("supplier__priority", "source__code", "-updated_at", "-id")
            )

        candidate: SupplierRawOffer | None = None
        for raw_offer in raw_offers:
            if raw_offer.supplier_id != selected_offer.supplier_id:
                continue
            external_sku = str(getattr(raw_offer, "external_sku", "") or "").strip()
            article = str(getattr(raw_offer, "article", "") or "").strip()
            normalized_article = str(getattr(raw_offer, "normalized_article", "") or "").strip()
            if offer_sku and (external_sku == offer_sku or article == offer_sku):
                candidate = raw_offer
                break
            if offer_sku_compact and (
                cls._normalize_compact(external_sku) == offer_sku_compact
                or cls._normalize_compact(article) == offer_sku_compact
                or cls._normalize_compact(normalized_article) == offer_sku_compact
            ):
                candidate = raw_offer
                break
            if candidate is None:
                candidate = raw_offer

        obj._backoffice_selected_raw_offer = candidate
        return candidate

    @staticmethod
    def _resolve_supplier_offers(obj: Product) -> list[SupplierOffer]:
        prefetched = getattr(obj, "backoffice_supplier_offers", None)
        if prefetched is not None:
            return list(prefetched)
        return list(
            SupplierOffer.objects.filter(product=obj)
            .select_related("supplier")
            .order_by("supplier__priority", "-updated_at", "id")
        )

    @staticmethod
    def _resolve_available_offers(obj: Product) -> list[SupplierOffer]:
        return [offer for offer in BackofficeCatalogProductSerializer._resolve_supplier_offers(obj) if offer.is_available]

    @classmethod
    def _resolve_productprice_status(cls, obj: Product) -> tuple[str, str]:
        product_price = cls._resolve_product_price(obj)
        if product_price is not None and product_price.final_price and product_price.final_price > 0:
            return "has_price", "product_price_present"

        offers = cls._resolve_supplier_offers(obj)
        if not offers:
            return "no_available_offer", "no_supplier_offers"

        available_offers = [offer for offer in offers if offer.is_available]
        if not available_offers:
            return "no_available_offer", "all_supplier_offers_unavailable"

        has_valid_available_offer = any((offer.purchase_price or 0) > 0 for offer in available_offers)
        if not has_valid_available_offer:
            return "invalid_offer", "available_offer_nonpositive_purchase_price"

        if product_price is None:
            return "no_product_price", "product_price_missing"

        if (product_price.final_price or 0) <= 0:
            return "invalid_offer", "product_price_nonpositive"

        return "no_product_price", "product_price_missing"

    @classmethod
    def _resolve_supplier_purchase_price(cls, obj: Product) -> tuple[Decimal | None, str | None]:
        offer = cls._resolve_supplier_offer(obj)
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

    def get_supplier_price_levels(self, obj: Product):
        prefetched = getattr(obj, "backoffice_raw_offers", None)
        raw_offers = prefetched
        if raw_offers is None:
            raw_offers = (
                obj.raw_supplier_offers.select_related("source", "supplier")
                .order_by("supplier__priority", "source__code", "-updated_at", "-id")
            )

        # GPL offers are now received as price_type_* fields; build readable
        # levels from raw payload first so ops sees wholesale tiers in admin.
        gpl_levels: list[dict] = []
        for raw_offer in raw_offers:
            source_code = str(getattr(raw_offer.source, "code", "") or "").lower()
            if source_code != "gpl":
                continue
            levels = extract_gpl_price_levels(item=raw_offer.raw_payload or {}, default_currency=raw_offer.currency)
            if levels and len(levels) > len(gpl_levels):
                gpl_levels = levels

        if gpl_levels:
            return gpl_levels

        prefetched_offers = getattr(obj, "backoffice_supplier_offers", None)
        offers = prefetched_offers
        if offers is None:
            offers = SupplierOffer.objects.filter(product=obj).select_related("supplier").order_by("supplier__priority", "-updated_at", "id")

        for offer in offers:
            if isinstance(offer.price_levels, list) and offer.price_levels:
                return offer.price_levels
        return []

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

        if source_code == "utr":
            # UTR admin display must keep all known warehouse labels visible,
            # including zero-quantity rows.
            utr_segments: list[dict] = []
            has_known_utr_keys = any(key in raw_payload for key in BackofficeCatalogProductSerializer.UTR_WAREHOUSE_COLUMNS)
            if has_known_utr_keys:
                for key in BackofficeCatalogProductSerializer.UTR_WAREHOUSE_COLUMNS:
                    raw_value = raw_payload.get(key, "")
                    normalized = str(raw_value).strip() if raw_value is not None else ""
                    if not normalized:
                        normalized = "0"
                    utr_segments.append(
                        {
                            "key": key,
                            "value": normalized,
                            "source_code": source_code,
                        }
                    )
                return utr_segments

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
        selected_offer = self._resolve_selected_offer(obj)
        if selected_offer is not None and selected_offer.supplier_sku:
            return selected_offer.supplier_sku

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
        return get_product_display_sku(obj)

    def get_supplier_offer_seen_at(self, obj: Product):
        prefetched = getattr(obj, "backoffice_supplier_offers", None)
        if prefetched is not None:
            offers = prefetched
        else:
            offers = SupplierOffer.objects.filter(product=obj).only("last_seen_at", "updated_at")

        seen_values = [
            offer.last_seen_at or offer.updated_at
            for offer in offers
            if offer.last_seen_at or offer.updated_at
        ]
        return max(seen_values) if seen_values else None

    def get_stock_qty(self, obj: Product) -> int:
        display_stock_qty = int(resolve_display_stock_qty(obj) or 0)
        if display_stock_qty > 0:
            return display_stock_qty

        offers = self._resolve_supplier_offers(obj)
        max_offer_stock = max((int(offer.stock_qty or 0) for offer in offers), default=0)
        if max_offer_stock > 0:
            return max_offer_stock

        raw_offers = getattr(obj, "backoffice_raw_offers", None)
        if raw_offers is None:
            raw_offers = (
                obj.raw_supplier_offers
                .only("stock_qty")
                .order_by("-updated_at", "-id")[:20]
            )
        max_raw_stock = max((int(getattr(raw_offer, "stock_qty", 0) or 0) for raw_offer in raw_offers), default=0)
        if max_raw_stock > 0:
            return max_raw_stock

        return display_stock_qty

    def get_supplier_offer_stock_sum(self, obj: Product) -> int:
        return get_available_supplier_offer_stock_sum(obj)

    def get_supplier_codes(self, obj: Product) -> list[str]:
        seen: set[str] = set()
        codes: list[str] = []
        for offer in self._resolve_supplier_offers(obj):
            code = str(getattr(offer.supplier, "code", "") or "").strip().lower()
            if not code or code in seen:
                continue
            seen.add(code)
            codes.append(code)
        return codes

    def get_primary_supplier_code(self, obj: Product) -> str:
        offer = self._resolve_selected_offer(obj) or self._resolve_supplier_offer(obj)
        if offer is None:
            return ""
        return str(getattr(offer.supplier, "code", "") or "").strip().lower()

    def get_supplier_code(self, obj: Product) -> str:
        return self.get_primary_supplier_code(obj)

    def get_selected_offer_supplier_code(self, obj: Product) -> str:
        offer = self._resolve_selected_offer(obj)
        if offer is None:
            return ""
        return str(getattr(offer.supplier, "code", "") or "").strip().lower()

    def get_selected_offer_supplier_sku(self, obj: Product) -> str:
        offer = self._resolve_selected_offer(obj)
        return str(getattr(offer, "supplier_sku", "") or "") if offer is not None else ""

    def get_selected_offer_purchase_price(self, obj: Product):
        offer = self._resolve_selected_offer(obj)
        if offer is None:
            return None
        value = self._as_decimal(getattr(offer, "purchase_price", None))
        return f"{value:.2f}" if value > 0 else None

    def get_selected_offer_stock_qty(self, obj: Product) -> int | None:
        offer = self._resolve_selected_offer(obj)
        if offer is None:
            return None
        return int(getattr(offer, "stock_qty", 0) or 0)

    def get_selected_offer_raw_article(self, obj: Product) -> str:
        raw_offer = self._resolve_selected_raw_offer(obj)
        if raw_offer is None:
            return ""
        payload = raw_offer.raw_payload if isinstance(raw_offer.raw_payload, dict) else {}
        return (
            str(payload.get("Артикул ТД") or "")
            or str(payload.get("Артикул ТД.") or "")
            or str(payload.get("manufacturer_article") or "")
            or str(payload.get("article_td") or "")
            or str(payload.get("Артикул") or "")
            or str(payload.get("article") or "")
            or str(getattr(raw_offer, "article", "") or "")
        ).strip()

    def get_selected_offer_raw_brand(self, obj: Product) -> str:
        raw_offer = self._resolve_selected_raw_offer(obj)
        if raw_offer is None:
            return ""
        payload = raw_offer.raw_payload if isinstance(raw_offer.raw_payload, dict) else {}
        return (
            str(payload.get("Бренд") or "")
            or str(payload.get("brand") or "")
            or str(getattr(raw_offer, "brand_name", "") or "")
        ).strip()

    def get_has_product_price(self, obj: Product) -> bool:
        return self._resolve_product_price(obj) is not None

    def get_has_available_offer(self, obj: Product) -> bool:
        return bool(self._resolve_available_offers(obj))

    def get_productprice_status(self, obj: Product) -> str:
        cached = getattr(obj, "_backoffice_productprice_status", None)
        if cached is None:
            cached = self._resolve_productprice_status(obj)
            obj._backoffice_productprice_status = cached
        status, _ = cached
        return status

    def get_productprice_status_reason(self, obj: Product) -> str:
        cached = getattr(obj, "_backoffice_productprice_status", None)
        if cached is None:
            cached = self._resolve_productprice_status(obj)
            obj._backoffice_productprice_status = cached
        _, reason = cached
        return reason

    def get_is_public(self, obj: Product) -> bool:
        return bool(obj.is_active and obj.published_at)

    def get_autodb_link_status(self, obj: Product) -> str:
        if not obj.autodb_supplier_id or not str(obj.autodb_article_number or "").strip():
            return "unlinked"

        link_quality_status = self._get_link_quality_status(obj)
        if link_quality_status == AutoDbProductLinkQuality.STATUS_TRUSTED:
            return "trusted"
        if link_quality_status == AutoDbProductLinkQuality.STATUS_SUSPICIOUS:
            return "suspicious"
        if link_quality_status == AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW:
            return "needs_review"
        return "linked"

    def get_compatibility_available(self, obj: Product) -> bool:
        return self.get_is_autodb_compatible_data_available(obj)

    @staticmethod
    def _parse_segment_qty(value: str) -> Decimal | None:
        normalized = re.sub(r"[^\d,.\-]", "", str(value or "")).replace(",", ".").strip()
        if not normalized:
            return None
        try:
            return Decimal(normalized)
        except Exception:
            return None

    def get_warehouse_summary(self, obj: Product) -> dict[str, int]:
        segments = self.get_warehouse_segments(obj)
        warehouse_total_count = len(segments)
        warehouse_nonzero_count = 0
        stock_qty_total = Decimal("0")
        for segment in segments:
            quantity = self._parse_segment_qty(str(segment.get("value", "") or ""))
            if quantity is None:
                continue
            stock_qty_total += quantity
            if quantity > 0:
                warehouse_nonzero_count += 1

        return {
            "warehouse_total_count": warehouse_total_count,
            "warehouse_nonzero_count": warehouse_nonzero_count,
            "stock_qty_total": int(stock_qty_total),
            "supplier_offer_stock_sum": self.get_supplier_offer_stock_sum(obj),
        }

    @classmethod
    def _resolve_utr_offer_price(cls, obj: Product) -> str | None:
        for offer in cls._resolve_supplier_offers(obj):
            supplier_code = str(getattr(getattr(offer, "supplier", None), "code", "") or "").strip().lower()
            if supplier_code != "utr":
                continue
            price = cls._as_decimal(getattr(offer, "purchase_price", None))
            if price > 0:
                return f"{price:.2f}"
        return None

    @classmethod
    def _resolve_gpl_rrc_price(cls, obj: Product) -> str | None:
        prefetched = getattr(obj, "backoffice_raw_offers", None)
        raw_offers = prefetched
        if raw_offers is None:
            raw_offers = (
                obj.raw_supplier_offers.select_related("source", "supplier")
                .filter(source__code="gpl")
                .order_by("supplier__priority", "-updated_at", "-id")
            )

        for raw_offer in raw_offers:
            source_code = str(getattr(getattr(raw_offer, "source", None), "code", "") or "").strip().lower()
            if source_code != "gpl":
                continue
            levels = extract_gpl_price_levels(item=raw_offer.raw_payload or {}, default_currency=raw_offer.currency)
            for level in levels:
                key = str(level.get("key", "") or "").strip().lower()
                label = str(level.get("label", "") or "").strip().lower()
                is_rrc = (
                    "ррц" in key
                    or "ррц" in label
                    or "rrc" in key
                    or "rrc" in label
                    or "rrp" in key
                    or "rrp" in label
                    or key == "price_type_10"
                )
                if not is_rrc:
                    continue
                value = cls._as_decimal(level.get("value"))
                if value > 0:
                    return f"{value:.2f}"
        return None

    def get_price_tooltip_summary(self, obj: Product) -> dict[str, object]:
        selected_supplier_price = self.get_selected_offer_purchase_price(obj) or self.get_supplier_price(obj)
        return {
            "final_price": self.get_final_price(obj),
            "selected_supplier_price": selected_supplier_price,
            "utr_price": self._resolve_utr_offer_price(obj),
            "gpl_rrc_price": self._resolve_gpl_rrc_price(obj),
            "markup_percent": self.get_applied_markup_percent(obj),
            "pricing_policy": self.get_applied_markup_policy_name(obj) or self.get_applied_markup_policy_scope(obj) or "",
            "updated_at": self.get_price_updated_at(obj) or obj.updated_at,
        }
