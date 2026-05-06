from rest_framework import serializers

from apps.catalog.models import Product, ProductAttribute, ProductImage
from apps.catalog.services.product_management import get_product_display_name
from apps.catalog.services.fitment_filtering import is_fitment_disabled_category
from apps.catalog.services.product_fitment_lookup import (
    get_autodb_fitment_queryset,
    get_utr_fitment_queryset,
    is_autodb_fitment_provider,
    resolve_product_utr_detail_ids,
    resolve_selected_autocatalog_vehicle,
    serialize_autodb_fitment_mapping,
    serialize_utr_fitment_mapping,
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
    brand = ProductBrandSerializer(read_only=True)
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

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "article",
            "name",
            "slug",
            "short_description",
            "description",
            "brand",
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
        )

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
        offers = obj.supplier_offers.all()
        total = 0
        for offer in offers:
            if not offer.is_available:
                continue
            total += max(int(offer.stock_qty or 0), 0)
        return total

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
        rows: list[dict] = []
        dedupe: set[tuple[str, str, str, str, str]] = set()

        for fitment in obj.fitments.all():
            if fitment.modification_id is None or str(fitment.source or "") == ProductFitment.SOURCE_AUTODB_PRO:
                continue
            row = {
                "id": str(fitment.id),
                "make": str(fitment.modification.engine.generation.model.make.name),
                "model": str(fitment.modification.engine.generation.model.name),
                "generation": str(fitment.modification.engine.generation.name),
                "engine": str(fitment.modification.engine.name),
                "modification": str(fitment.modification.name),
                "note": str(fitment.note or ""),
                "is_exact": bool(fitment.is_exact),
            }
            key = (row["make"], row["model"], row["generation"], row["engine"], row["modification"])
            if key in dedupe:
                continue
            dedupe.add(key)
            rows.append(row)

        selected_vehicle = resolve_selected_autocatalog_vehicle(self.context.get("request"))
        selected_model_key = None
        if selected_vehicle is not None:
            selected_model_key = (selected_vehicle.make_name, selected_vehicle.model_name)

        if is_autodb_fitment_provider():
            if not self._is_autodb_linked(obj):
                return rows
            autodb_maps = get_autodb_fitment_queryset(product=obj, selected_vehicle=selected_vehicle)
            for mapping in autodb_maps.iterator(chunk_size=200):
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
            return rows

        utr_detail_ids = resolve_product_utr_detail_ids(product=obj)
        if not utr_detail_ids:
            return rows

        utr_maps = get_utr_fitment_queryset(detail_ids=utr_detail_ids, selected_vehicle=selected_vehicle)
        for mapping in utr_maps.iterator(chunk_size=200):
            row = serialize_utr_fitment_mapping(mapping)
            key = (row["make"], row["model"], row["generation"], row["engine"], row["modification"])
            if key in dedupe:
                continue
            dedupe.add(key)
            rows.append(row)
            if selected_model_key is not None and (row["make"], row["model"]) == selected_model_key:
                continue
            if len(rows) >= 80:
                break

        return rows

    def get_fitment_badge_hidden(self, obj: Product) -> bool:
        cached = getattr(obj, "_fitment_badge_hidden", None)
        if cached is not None:
            return bool(cached)
        hidden = is_fitment_disabled_category(getattr(obj, "category", None))
        setattr(obj, "_fitment_badge_hidden", hidden)
        return hidden
