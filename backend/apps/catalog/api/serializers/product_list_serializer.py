from django.db.models import Q
from rest_framework import serializers

from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.catalog.services.autodb_content import get_autodb_primary_image_url
from apps.catalog.services.product_management import get_product_display_name
from apps.catalog.services.product_branding import get_product_display_brand_payload
from apps.catalog.services.product_sku import get_product_display_sku, get_product_manufacturer_article
from apps.catalog.services.product_stock import resolve_display_stock_qty
from apps.catalog.services.product_fitment_lookup import (
    get_public_autodb_fitment_ids,
    resolve_selected_passanger_car_id,
)
from apps.catalog.services.category_vehicle_filter_policy import get_vehicle_filter_policy
from apps.pricing.models import SupplierOffer
from apps.pricing.services import ProductSellableSnapshotService
from apps.supplier_imports.models import SupplierRawOffer

from .product_shared_serializer import ProductBrandSerializer, ProductCategorySerializer

sellable_service = ProductSellableSnapshotService()


class ProductListSerializer(serializers.ModelSerializer):
    sku = serializers.SerializerMethodField()
    article = serializers.SerializerMethodField()
    manufacturer_article = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    display_brand = serializers.SerializerMethodField()
    brand_source = serializers.SerializerMethodField()
    category = ProductCategorySerializer(read_only=True)
    primary_image = serializers.SerializerMethodField()
    final_price = serializers.DecimalField(
        source="product_price.final_price",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    currency = serializers.CharField(source="product_price.currency", read_only=True)
    availability_status = serializers.SerializerMethodField()
    availability_label = serializers.SerializerMethodField()
    estimated_delivery_days = serializers.SerializerMethodField()
    procurement_source_summary = serializers.SerializerMethodField()
    selected_offer_supplier_code = serializers.SerializerMethodField()
    selected_offer_supplier_sku = serializers.SerializerMethodField()
    selected_offer_purchase_price = serializers.SerializerMethodField()
    selected_offer_stock_qty = serializers.SerializerMethodField()
    selected_offer_raw_article = serializers.SerializerMethodField()
    selected_offer_raw_brand = serializers.SerializerMethodField()
    is_sellable = serializers.SerializerMethodField()
    total_stock_qty = serializers.SerializerMethodField()
    has_fitment_data = serializers.BooleanField(read_only=True, default=False)
    fits_selected_vehicle = serializers.BooleanField(read_only=True, allow_null=True, default=None)
    fitment_count = serializers.SerializerMethodField()
    is_autodb_compatible_data_available = serializers.SerializerMethodField()
    link_quality_status = serializers.SerializerMethodField()
    vehicle_filter_policy = serializers.SerializerMethodField()
    selected_vehicle_compatibility = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "article",
            "manufacturer_article",
            "name",
            "slug",
            "short_description",
            "brand",
            "display_brand",
            "brand_source",
            "category",
            "primary_image",
            "final_price",
            "currency",
            "availability_status",
            "availability_label",
            "estimated_delivery_days",
            "procurement_source_summary",
            "selected_offer_supplier_code",
            "selected_offer_supplier_sku",
            "selected_offer_purchase_price",
            "selected_offer_stock_qty",
            "selected_offer_raw_article",
            "selected_offer_raw_brand",
            "is_sellable",
            "total_stock_qty",
            "is_featured",
            "is_new",
            "is_bestseller",
            "has_fitment_data",
            "fits_selected_vehicle",
            "fitment_count",
            "is_autodb_compatible_data_available",
            "link_quality_status",
            "vehicle_filter_policy",
            "selected_vehicle_compatibility",
        )

    def get_sku(self, obj: Product) -> str:
        return get_product_display_sku(obj)

    def get_article(self, obj: Product) -> str:
        return get_product_manufacturer_article(obj)

    def get_manufacturer_article(self, obj: Product) -> str:
        return get_product_manufacturer_article(obj)

    def get_primary_image(self, obj: Product) -> str:
        primary_row = None
        primary_images = getattr(obj, "primary_images", None)
        if primary_images:
            primary_row = primary_images[0]
        if primary_row is None:
            all_images = getattr(obj, "all_images", None)
            if all_images:
                primary_row = all_images[0]

        if primary_row is not None:
            image = getattr(primary_row, "image", None)
            if image:
                try:
                    return image.url
                except Exception:  # noqa: BLE001
                    pass
            remote_url = str(getattr(primary_row, "remote_url", "") or "").strip()
            if remote_url:
                return remote_url

        if not obj.autodb_supplier_id or not str(obj.autodb_article_number or "").strip():
            return ""
        return get_autodb_primary_image_url(product=obj)

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

    def get_name(self, obj: Product) -> str:
        return get_product_display_name(obj, self._resolve_locale())

    def _brand_payload(self, obj: Product):
        return get_product_display_brand_payload(obj)

    def get_brand(self, obj: Product) -> dict:
        brand = getattr(obj, "brand", None)
        if brand is None:
            return {"id": "", "name": self._brand_payload(obj).display_brand, "slug": ""}
        serializer = ProductBrandSerializer(
            instance=brand,
            context={**self.context, "product": obj},
        )
        return serializer.data

    def get_display_brand(self, obj: Product) -> str:
        return self._brand_payload(obj).display_brand

    def get_brand_source(self, obj: Product) -> str:
        return self._brand_payload(obj).brand_source

    def _snapshot(self, obj: Product):
        cached = getattr(obj, "_sellable_snapshot", None)
        if cached is not None:
            return cached
        snapshot = sellable_service.build(product=obj, quantity=1)
        setattr(obj, "_sellable_snapshot", snapshot)
        return snapshot

    def get_availability_status(self, obj: Product) -> str:
        return self._snapshot(obj).availability_status

    def get_availability_label(self, obj: Product) -> str:
        return self._snapshot(obj).availability_label

    def get_estimated_delivery_days(self, obj: Product) -> int | None:
        return self._snapshot(obj).estimated_delivery_days

    def get_procurement_source_summary(self, obj: Product) -> str:
        return self._snapshot(obj).procurement_source_summary

    def _selected_offer(self, obj: Product) -> SupplierOffer | None:
        if hasattr(obj, "_public_selected_offer"):
            return getattr(obj, "_public_selected_offer")
        snapshot = self._snapshot(obj)
        selected_offer_id = str(snapshot.selected_offer_id or "").strip()
        if not selected_offer_id:
            obj._public_selected_offer = None
            return None
        offer = SupplierOffer.objects.select_related("supplier").filter(id=selected_offer_id).first()
        obj._public_selected_offer = offer
        return offer

    def _selected_raw_offer(self, obj: Product) -> SupplierRawOffer | None:
        if hasattr(obj, "_public_selected_raw_offer"):
            return getattr(obj, "_public_selected_raw_offer")
        selected_offer = self._selected_offer(obj)
        if selected_offer is None:
            obj._public_selected_raw_offer = None
            return None
        supplier_sku = str(getattr(selected_offer, "supplier_sku", "") or "").strip()
        raw_offer = (
            SupplierRawOffer.objects.filter(matched_product=obj, supplier=selected_offer.supplier)
            .filter(
                Q(external_sku=supplier_sku)
                | Q(article=supplier_sku)
                | Q(external_sku__icontains=supplier_sku)
                | Q(article__icontains=supplier_sku)
            )
            .order_by("-updated_at", "-id")
            .first()
        )
        if raw_offer is None:
            raw_offer = (
                SupplierRawOffer.objects.filter(matched_product=obj, supplier=selected_offer.supplier)
                .order_by("-updated_at", "-id")
                .first()
            )
        obj._public_selected_raw_offer = raw_offer
        return raw_offer

    def get_selected_offer_supplier_code(self, obj: Product) -> str:
        offer = self._selected_offer(obj)
        if offer is None:
            return ""
        return str(getattr(offer.supplier, "code", "") or "").strip().lower()

    def get_selected_offer_supplier_sku(self, obj: Product) -> str:
        offer = self._selected_offer(obj)
        return str(getattr(offer, "supplier_sku", "") or "") if offer is not None else ""

    def get_selected_offer_purchase_price(self, obj: Product):
        offer = self._selected_offer(obj)
        if offer is None or not offer.purchase_price:
            return None
        return f"{offer.purchase_price:.2f}"

    def get_selected_offer_stock_qty(self, obj: Product) -> int | None:
        offer = self._selected_offer(obj)
        if offer is None:
            return None
        return int(getattr(offer, "stock_qty", 0) or 0)

    def get_selected_offer_raw_article(self, obj: Product) -> str:
        raw_offer = self._selected_raw_offer(obj)
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
        raw_offer = self._selected_raw_offer(obj)
        if raw_offer is None:
            return ""
        payload = raw_offer.raw_payload if isinstance(raw_offer.raw_payload, dict) else {}
        return (
            str(payload.get("Бренд") or "")
            or str(payload.get("brand") or "")
            or str(getattr(raw_offer, "brand_name", "") or "")
        ).strip()

    def get_is_sellable(self, obj: Product) -> bool:
        return self._snapshot(obj).is_sellable

    def get_total_stock_qty(self, obj: Product) -> int:
        return resolve_display_stock_qty(obj)

    def _get_link_quality_status(self, obj: Product) -> str:
        article_key = str(getattr(obj, "autodb_article_key", "") or "").strip()
        if not article_key:
            return ""
        quality = (
            AutoDbProductLinkQuality.objects.filter(product=obj, autodb_article_key=article_key)
            .order_by("-checked_at", "-updated_at")
            .values_list("status", flat=True)
            .first()
        )
        return str(quality or "")

    def get_link_quality_status(self, obj: Product) -> str:
        return self._get_link_quality_status(obj)

    def get_vehicle_filter_policy(self, obj: Product) -> str:
        return get_vehicle_filter_policy(getattr(obj, "category", None))

    def get_fitment_count(self, obj: Product) -> int:
        return len(set(get_public_autodb_fitment_ids(product=obj)))

    def get_is_autodb_compatible_data_available(self, obj: Product) -> bool:
        return self.get_fitment_count(obj) > 0

    def get_selected_vehicle_compatibility(self, obj: Product) -> dict | None:
        request = self.context.get("request")
        selected_vehicle_id = resolve_selected_passanger_car_id(request)
        if not selected_vehicle_id:
            return None
        return {
            "vehicle_id": int(selected_vehicle_id),
            "is_compatible": bool(getattr(obj, "fits_selected_vehicle", False)),
        }
