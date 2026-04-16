from rest_framework import serializers

from apps.catalog.models import Product, ProductAttribute, ProductImage
from apps.pricing.services import ProductSellableSnapshotService

from .product_shared_serializer import ProductBrandSerializer, ProductCategorySerializer

sellable_service = ProductSellableSnapshotService()


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ("id", "image_url", "alt_text", "is_primary", "sort_order")

    def get_image_url(self, obj: ProductImage) -> str:
        request = self.context.get("request")
        if request is None:
            return obj.image.url
        return request.build_absolute_uri(obj.image.url)


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
    id = serializers.UUIDField(read_only=True)
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
    images = ProductImageSerializer(many=True, read_only=True)
    attributes = ProductAttributeSerializer(source="product_attributes", many=True, read_only=True)
    fitments = ProductFitmentSerializer(many=True, read_only=True)
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
            "is_featured",
            "is_new",
            "is_bestseller",
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
