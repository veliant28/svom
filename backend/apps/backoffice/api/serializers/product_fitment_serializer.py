from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import Product
from apps.compatibility.models import ProductFitment
from apps.vehicles.models import VehicleModification
from apps.vehicles.services import normalize_vehicle_name


class BackofficeProductFitmentSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.select_related("brand", "category"))
    modification = serializers.PrimaryKeyRelatedField(
        queryset=VehicleModification.objects.select_related(
            "engine",
            "engine__generation",
            "engine__generation__model",
            "engine__generation__model__make",
        ),
    )

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    modification_name = serializers.CharField(source="modification.name", read_only=True)
    engine_name = serializers.CharField(source="modification.engine.name", read_only=True)
    generation_name = serializers.CharField(source="modification.engine.generation.name", read_only=True)
    model_name = serializers.CharField(source="modification.engine.generation.model.name", read_only=True)
    make_name = serializers.CharField(source="modification.engine.generation.model.make.name", read_only=True)

    class Meta:
        model = ProductFitment
        fields = (
            "id",
            "product",
            "product_name",
            "product_sku",
            "modification",
            "modification_name",
            "engine_name",
            "generation_name",
            "model_name",
            "make_name",
            "note",
            "is_exact",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "product_name",
            "product_sku",
            "modification_name",
            "engine_name",
            "generation_name",
            "model_name",
            "make_name",
        )
        extra_kwargs = {
            "note": {"required": False, "allow_blank": True},
        }

    def validate_note(self, value: str) -> str:
        return normalize_vehicle_name(value)

    def validate(self, attrs):
        instance: ProductFitment | None = getattr(self, "instance", None)
        product = attrs.get("product", instance.product if instance is not None else None)
        modification = attrs.get("modification", instance.modification if instance is not None else None)
        if product is None or modification is None:
            return attrs

        duplicate_query = ProductFitment.objects.filter(product=product, modification=modification)
        if instance is not None:
            duplicate_query = duplicate_query.exclude(id=instance.id)
        if duplicate_query.exists():
            raise serializers.ValidationError(
                {"modification": "Для выбранного товара эта модификация уже добавлена."},
            )

        if "note" in attrs:
            attrs["note"] = normalize_vehicle_name(attrs["note"])
        return attrs
