import re

from django.db import IntegrityError, transaction
from rest_framework import serializers

from apps.autodb.selectors import get_passanger_car, get_vehicle_manufacturer, get_vehicle_model
from apps.users.models import GarageVehicle

_WS_RE = re.compile(r"[\n\r\t]+")
_MULTI_SPACE_RE = re.compile(r"\s+")


def _clean_text(value: str | None) -> str:
    normalized = _WS_RE.sub(" ", str(value or ""))
    normalized = _MULTI_SPACE_RE.sub(" ", normalized)
    return normalized.strip()


def _contains_ci(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    return needle.lower() in haystack.lower()


class GarageVehicleCreateSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    autodb_manufacturer_id = serializers.IntegerField(required=False, allow_null=True)
    autodb_model_id = serializers.IntegerField(required=False, allow_null=True)
    autodb_passanger_car_id = serializers.IntegerField(required=False, allow_null=True)
    autodb_vehicle_label = serializers.CharField(required=False, allow_blank=True)
    autodb_modification = serializers.CharField(required=False, allow_blank=True)
    autodb_engine = serializers.CharField(required=False, allow_blank=True)
    autodb_power_hp = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    autodb_power_kw = serializers.IntegerField(required=False, allow_null=True, min_value=0)

    class Meta:
        model = GarageVehicle
        fields = (
            "id",
            "year",
            "autodb_manufacturer_id",
            "autodb_model_id",
            "autodb_passanger_car_id",
            "autodb_vehicle_label",
            "autodb_modification",
            "autodb_engine",
            "autodb_power_hp",
            "autodb_power_kw",
            "catalog_source",
            "is_primary",
        )
        read_only_fields = ("id", "catalog_source")
        validators = []

    def validate(self, attrs):
        request = self.context["request"]
        attrs["user"] = request.user

        autodb_passanger_car_id = attrs.get("autodb_passanger_car_id")
        if autodb_passanger_car_id is None:
            raise serializers.ValidationError("autodb_passanger_car_id is required.")

        attrs["make"] = None
        attrs["model"] = None
        attrs["generation"] = None
        attrs["engine"] = None
        attrs["modification"] = None
        attrs["nickname"] = ""
        attrs["vin"] = ""

        autodb_manufacturer_id = attrs.get("autodb_manufacturer_id")
        autodb_model_id = attrs.get("autodb_model_id")
        if autodb_manufacturer_id is None or autodb_model_id is None:
            raise serializers.ValidationError(
                "autodb_manufacturer_id and autodb_model_id are required for Auto_DB_Pro flow."
            )

        passanger_car = get_passanger_car(passanger_car_id=autodb_passanger_car_id)
        if not passanger_car:
            raise serializers.ValidationError("Auto_DB_Pro passanger car is not found.")

        resolved_model_id = int(passanger_car.get("model_id") or 0)
        if resolved_model_id != int(autodb_model_id):
            raise serializers.ValidationError("autodb_model_id does not match selected passanger car.")

        manufacturer = get_vehicle_manufacturer(autodb_manufacturer_id)
        model = get_vehicle_model(manufacturer_id=autodb_manufacturer_id, model_id=autodb_model_id)
        if model is None:
            raise serializers.ValidationError("Auto_DB_Pro model is not found for provided manufacturer.")

        year_from = passanger_car.get("year_from")
        year_to = passanger_car.get("year_to")
        selected_year = attrs.get("year")
        if isinstance(selected_year, int) and selected_year > 0:
            if isinstance(year_from, int) and selected_year < year_from:
                raise serializers.ValidationError("Selected year is outside of the selected vehicle interval.")
            if isinstance(year_to, int) and selected_year > year_to:
                raise serializers.ValidationError("Selected year is outside of the selected vehicle interval.")
            resolved_year = selected_year
        else:
            resolved_year = int(year_from) if isinstance(year_from, int) else None

        year_label = ""
        if isinstance(resolved_year, int):
            year_label = str(resolved_year)
        elif year_from and year_to:
            year_label = f"{year_from}-{year_to}"
        elif year_from:
            year_label = str(year_from)

        manufacturer_name = _clean_text((manufacturer or {}).get("name") or "")
        model_name = _clean_text(model.get("description") or model.get("name") or "")
        passanger_name = _clean_text(passanger_car.get("description") or passanger_car.get("name") or "")
        selected_modification = _clean_text(attrs.get("autodb_modification") or passanger_name)
        selected_engine = _clean_text(attrs.get("autodb_engine") or "")
        passanger_includes_make_or_model = _contains_ci(passanger_name, manufacturer_name) or _contains_ci(passanger_name, model_name)
        title_core = passanger_name if passanger_name and passanger_includes_make_or_model else _clean_text(
            " ".join(part for part in [manufacturer_name, model_name, passanger_name] if part)
        )
        title_label = title_core
        if selected_engine and not _contains_ci(title_core, selected_engine):
            title_label = _clean_text(" ".join(part for part in [title_core, selected_engine] if part))

        generated_label = _clean_text(", ".join(part for part in [title_label, year_label] if part))

        attrs["year"] = resolved_year
        attrs["catalog_source"] = GarageVehicle.CATALOG_SOURCE_AUTODB_PRO
        attrs["autodb_vehicle_label"] = _clean_text(attrs.get("autodb_vehicle_label") or generated_label)
        attrs["autodb_modification"] = selected_modification
        attrs["autodb_engine"] = selected_engine
        attrs["autodb_power_hp"] = attrs.get("autodb_power_hp")
        attrs["autodb_power_kw"] = attrs.get("autodb_power_kw")
        return attrs

    def create(self, validated_data):
        user = validated_data["user"]
        is_primary = validated_data.get("is_primary", False)
        autodb_passanger_car_id = validated_data.get("autodb_passanger_car_id")

        with transaction.atomic():
            existing = None
            if autodb_passanger_car_id is not None:
                existing = GarageVehicle.objects.filter(
                    user=user,
                    autodb_passanger_car_id=autodb_passanger_car_id,
                ).first()

            if is_primary:
                primary_qs = GarageVehicle.objects.filter(user=user, is_primary=True)
                if existing is not None:
                    primary_qs = primary_qs.exclude(pk=existing.pk)
                primary_qs.update(is_primary=False)

            if existing is not None:
                update_fields: list[str] = []
                for field in (
                    "year",
                    "catalog_source",
                    "autodb_manufacturer_id",
                    "autodb_model_id",
                    "autodb_passanger_car_id",
                    "autodb_vehicle_label",
                    "autodb_modification",
                    "autodb_engine",
                    "autodb_power_hp",
                    "autodb_power_kw",
                ):
                    next_value = validated_data.get(field)
                    if getattr(existing, field) != next_value:
                        setattr(existing, field, next_value)
                        update_fields.append(field)

                if is_primary and not existing.is_primary:
                    existing.is_primary = True
                    update_fields.append("is_primary")
                if update_fields:
                    update_fields.append("updated_at")
                    existing.save(update_fields=tuple(update_fields))
                return existing

            try:
                return GarageVehicle.objects.create(**validated_data)
            except IntegrityError:
                return GarageVehicle.objects.get(user=user, autodb_passanger_car_id=autodb_passanger_car_id)
