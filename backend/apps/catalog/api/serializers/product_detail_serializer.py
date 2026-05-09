from rest_framework import serializers

from apps.catalog.models import AutoDbProductLinkQuality, Product, ProductAttribute, ProductImage
from apps.catalog.services.product_management import get_product_display_name
from apps.catalog.services.product_branding import get_product_display_brand_payload
from apps.catalog.services.product_sku import get_product_display_sku, get_product_manufacturer_article
from apps.catalog.services.category_vehicle_filter_policy import get_vehicle_filter_policy
from apps.catalog.services.product_stock import resolve_display_stock_qty
from apps.catalog.services.product_fitment_lookup import (
    get_autodb_fitment_queryset,
    get_public_autodb_fitment_ids,
    resolve_public_autodb_vehicle_map,
    resolve_selected_autodb_vehicle_display,
    resolve_selected_autocatalog_vehicle,
    serialize_autodb_fitment_mapping,
    serialize_autodb_fitment_mapping_from_selector,
    serialize_autodb_fitment_fallback_row,
)
from apps.compatibility.models import ProductFitment
from apps.catalog.services.autodb_content import build_autodb_characteristic_attributes, get_autodb_product_content
from apps.pricing.services import ProductSellableSnapshotService

from .product_shared_serializer import ProductBrandSerializer, ProductCategorySerializer

sellable_service = ProductSellableSnapshotService()


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ("id", "image_url", "alt_text", "is_primary", "sort_order")

    def get_image_url(self, obj: ProductImage) -> str:
        if getattr(obj, "image", None):
            try:
                return obj.image.url
            except Exception:  # noqa: BLE001
                pass
        return str(getattr(obj, "remote_url", "") or "")


class ProductAttributeSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source="attribute.name", read_only=True)
    value = serializers.SerializerMethodField()

    class Meta:
        model = ProductAttribute
        fields = ("id", "attribute_name", "value")

    def get_value(self, obj: ProductAttribute) -> str:
        if obj.attribute_value is not None:
            return obj.attribute_value.value
        return obj.raw_value


class ProductFitmentSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    make = serializers.CharField(source="modification.engine.generation.model.make.name", read_only=True)
    model = serializers.CharField(source="modification.engine.generation.model.name", read_only=True)
    generation = serializers.CharField(source="modification.engine.generation.name", read_only=True)
    engine = serializers.CharField(source="modification.engine.name", read_only=True)
    modification = serializers.CharField(source="modification.name", read_only=True)
    note = serializers.CharField(read_only=True)
    is_exact = serializers.BooleanField(read_only=True)


class ProductDetailSerializer(serializers.ModelSerializer):
    sku = serializers.SerializerMethodField()
    article = serializers.SerializerMethodField()
    manufacturer_article = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    display_brand = serializers.SerializerMethodField()
    brand_source = serializers.SerializerMethodField()
    category = ProductCategorySerializer(read_only=True)
    name = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    attributes = serializers.SerializerMethodField()
    fitments = serializers.SerializerMethodField()
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
    is_sellable = serializers.SerializerMethodField()
    total_stock_qty = serializers.SerializerMethodField()
    has_fitment_data = serializers.BooleanField(read_only=True, default=False)
    fits_selected_vehicle = serializers.BooleanField(read_only=True, allow_null=True, default=None)
    fitment_badge_hidden = serializers.SerializerMethodField()
    fitment_count = serializers.SerializerMethodField()
    is_autodb_compatible_data_available = serializers.SerializerMethodField()
    link_quality_status = serializers.SerializerMethodField()
    vehicle_filter_policy = serializers.SerializerMethodField()
    compatibility_summary = serializers.SerializerMethodField()

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
            "description",
            "brand",
            "display_brand",
            "brand_source",
            "category",
            "images",
            "attributes",
            "fitments",
            "final_price",
            "currency",
            "availability_status",
            "availability_label",
            "estimated_delivery_days",
            "procurement_source_summary",
            "is_sellable",
            "total_stock_qty",
            "is_featured",
            "is_new",
            "is_bestseller",
            "has_fitment_data",
            "fits_selected_vehicle",
            "fitment_badge_hidden",
            "fitment_count",
            "is_autodb_compatible_data_available",
            "link_quality_status",
            "vehicle_filter_policy",
            "compatibility_summary",
        )

    def get_sku(self, obj: Product) -> str:
        return get_product_display_sku(obj)

    def get_article(self, obj: Product) -> str:
        return get_product_manufacturer_article(obj)

    def get_manufacturer_article(self, obj: Product) -> str:
        return get_product_manufacturer_article(obj)

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

    def get_is_sellable(self, obj: Product) -> bool:
        return self._snapshot(obj).is_sellable

    def get_total_stock_qty(self, obj: Product) -> int:
        return resolve_display_stock_qty(obj)

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

    @staticmethod
    def _is_autodb_linked(product: Product) -> bool:
        return bool(product.autodb_supplier_id and str(product.autodb_article_number or "").strip())

    def get_images(self, obj: Product) -> list[dict]:
        image_serializer = ProductImageSerializer(context=self.context)
        rows: list[dict] = []
        seen_urls: set[str] = set()

        for image in obj.images.all():
            url = image_serializer.get_image_url(image)
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            rows.append(
                {
                    "id": str(image.id),
                    "image_url": url,
                    "alt_text": str(image.alt_text or ""),
                    "is_primary": bool(image.is_primary),
                    "sort_order": int(image.sort_order or 0),
                }
            )

        if self._is_autodb_linked(obj):
            autodb_content = get_autodb_product_content(product=obj, prefer_live=True)
            for index, url in enumerate(autodb_content.image_urls):
                clean_url = str(url or "").strip()
                if not clean_url or clean_url in seen_urls:
                    continue
                seen_urls.add(clean_url)
                rows.append(
                    {
                        "id": f"autodb-{obj.id}-{index}",
                        "image_url": clean_url,
                        "alt_text": str(get_product_display_name(obj, self._resolve_locale()) or obj.name)[:255],
                        "is_primary": not rows,
                        "sort_order": len(rows),
                    }
                )
                if len(rows) >= 12:
                    break

        return rows

    def get_attributes(self, obj: Product) -> list[dict]:
        local_rows = ProductAttributeSerializer(obj.product_attributes.all(), many=True, context=self.context).data
        if not self._is_autodb_linked(obj):
            return local_rows
        existing_names = {str(row.get("attribute_name") or "").strip().lower() for row in local_rows}
        autodb_rows = [
            row
            for row in build_autodb_characteristic_attributes(product=obj)
            if str(row.get("attribute_name") or "").strip().lower() not in existing_names
        ]
        return [*local_rows, *autodb_rows]

    def get_fitments(self, obj: Product) -> list[dict]:
        cached = getattr(obj, "_resolved_public_fitments", None)
        if cached is not None:
            return cached
        if not self._is_autodb_linked(obj):
            return []
        if self._get_link_quality_status(obj) != AutoDbProductLinkQuality.STATUS_TRUSTED:
            return []

        rows: list[dict] = []
        dedupe: set[tuple[str, str, str, str, str]] = set()
        selected_vehicle_display = resolve_selected_autodb_vehicle_display(self.context.get("request"))

        selected_vehicle = resolve_selected_autocatalog_vehicle(self.context.get("request"))
        selected_model_key = None
        if selected_vehicle is not None:
            selected_model_key = (selected_vehicle.make_name, selected_vehicle.model_name)
        autodb_maps = get_autodb_fitment_queryset(product=obj, selected_vehicle=selected_vehicle)
        for mapping in autodb_maps:
            row = serialize_autodb_fitment_mapping(mapping)
            key = (row["make"], row["model"], row["generation"], row["engine"], row["modification"])
            if key in dedupe:
                continue
            dedupe.add(key)
            rows.append(row)
            if selected_model_key is not None and (row["make"], row["model"]) == selected_model_key:
                continue
            if len(rows) >= 80:
                break

        if not rows:
            fitment_ids = get_public_autodb_fitment_ids(product=obj)
            vehicle_map = resolve_public_autodb_vehicle_map(passanger_car_ids=fitment_ids)
            for car_id in sorted(set(fitment_ids)):
                vehicle = vehicle_map.get(car_id)
                if vehicle is not None:
                    rows.append(serialize_autodb_fitment_mapping_from_selector(vehicle))
                else:
                    rows.append(serialize_autodb_fitment_fallback_row(passanger_car_id=car_id, selected_vehicle=selected_vehicle_display))
                if len(rows) >= 80:
                    break

        setattr(obj, "_resolved_public_fitments", rows)
        return rows

    def get_fitment_badge_hidden(self, obj: Product) -> bool:
        return False

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
        if self._get_link_quality_status(obj) != AutoDbProductLinkQuality.STATUS_TRUSTED:
            return 0
        return (
            ProductFitment.objects.filter(
                product=obj,
                source=ProductFitment.SOURCE_AUTODB_PRO,
                is_stale=False,
                excluded_from_public_filtering=False,
                quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            )
            .exclude(autodb_passanger_car_id__isnull=True)
            .values("autodb_passanger_car_id")
            .distinct()
            .count()
        )

    def get_is_autodb_compatible_data_available(self, obj: Product) -> bool:
        if not self._is_autodb_linked(obj):
            return False
        if self._get_link_quality_status(obj) != AutoDbProductLinkQuality.STATUS_TRUSTED:
            return False
        if self.get_fitment_count(obj) > 0:
            return True
        return ProductAttribute.objects.filter(
            product=obj,
            source=ProductAttribute.SOURCE_AUTODB_PRO,
        ).exists()

    def get_compatibility_summary(self, obj: Product) -> dict:
        if not self._is_autodb_linked(obj):
            return {
                "available": False,
                "fitment_count": 0,
                "selected_vehicle": None,
                "sample_vehicles": [],
            }
        if self._get_link_quality_status(obj) != AutoDbProductLinkQuality.STATUS_TRUSTED:
            return {
                "available": False,
                "fitment_count": 0,
                "selected_vehicle": None,
                "sample_vehicles": [],
            }

        fitment_ids = set(get_public_autodb_fitment_ids(product=obj))
        selected_vehicle = resolve_selected_autodb_vehicle_display(self.context.get("request"))
        selected_vehicle_payload = None
        if selected_vehicle is not None:
            selected_vehicle_id = int(selected_vehicle.get("vehicle_id") or 0)
            selected_vehicle_payload = {
                "vehicle_id": selected_vehicle_id,
                "is_compatible": selected_vehicle_id in fitment_ids,
                "label": str(selected_vehicle.get("label") or ""),
                "subtitle": str(selected_vehicle.get("subtitle") or ""),
                "make": str(selected_vehicle.get("make") or ""),
                "model": str(selected_vehicle.get("model") or ""),
                "modification": str(selected_vehicle.get("modification") or ""),
                "years": str(selected_vehicle.get("years") or ""),
                "engine": str(selected_vehicle.get("engine") or ""),
            }

        sample_vehicles: list[dict] = []
        for row in self.get_fitments(obj)[:10]:
            vehicle_id = int(row.get("vehicle_id") or int(str(row.get("id", "")).replace("autodb-", "") or 0))
            sample_vehicles.append(
                {
                    "vehicle_id": vehicle_id,
                    "make": str(row.get("make") or ""),
                    "model": str(row.get("model") or ""),
                    "modification": str(row.get("modification") or ""),
                    "years": str(row.get("generation") or ""),
                    "engine": str(row.get("engine") or ""),
                    "body": str(row.get("body") or ""),
                    "label": str(row.get("label") or ""),
                    "subtitle": str(row.get("subtitle") or ""),
                }
            )

        return {
            "available": bool(fitment_ids),
            "fitment_count": len(fitment_ids),
            "selected_vehicle": selected_vehicle_payload,
            "sample_vehicles": sample_vehicles,
        }
