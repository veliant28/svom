import re
from typing import Any

from rest_framework import serializers

from apps.autodb.selectors import get_passanger_car, get_vehicle_manufacturer, get_vehicle_model
from apps.users.models import GarageVehicle

_WS_RE = re.compile(r"[\n\r\t]+")
_MULTI_SPACE_RE = re.compile(r"\s+")


def _clean_text(value: Any) -> str:
    normalized = _WS_RE.sub(" ", str(value or ""))
    normalized = _MULTI_SPACE_RE.sub(" ", normalized)
    return normalized.strip()


class GarageVehicleListSerializer(serializers.ModelSerializer):
    car_modification_id = serializers.IntegerField(read_only=True, allow_null=True)
    catalog_source = serializers.CharField(read_only=True)
    autodb_manufacturer_id = serializers.IntegerField(read_only=True, allow_null=True)
    autodb_model_id = serializers.IntegerField(read_only=True, allow_null=True)
    autodb_passanger_car_id = serializers.IntegerField(read_only=True, allow_null=True)
    autodb_vehicle_label = serializers.CharField(read_only=True)
    autodb_modification = serializers.CharField(read_only=True)
    autodb_engine = serializers.CharField(read_only=True)
    autodb_power_hp = serializers.IntegerField(read_only=True, allow_null=True)
    autodb_power_kw = serializers.IntegerField(read_only=True, allow_null=True)

    brand = serializers.SerializerMethodField()
    model = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()
    period = serializers.SerializerMethodField()
    modification = serializers.SerializerMethodField()
    engine = serializers.SerializerMethodField()
    power_hp = serializers.SerializerMethodField()
    power_kw = serializers.SerializerMethodField()
    vehicle_label = serializers.SerializerMethodField()

    class Meta:
        model = GarageVehicle
        fields = (
            "id",
            "user",
            "catalog_source",
            "car_modification_id",
            "autodb_manufacturer_id",
            "autodb_model_id",
            "autodb_passanger_car_id",
            "autodb_vehicle_label",
            "autodb_modification",
            "autodb_engine",
            "autodb_power_hp",
            "autodb_power_kw",
            "vehicle_label",
            "brand",
            "model",
            "year",
            "period",
            "modification",
            "engine",
            "power_hp",
            "power_kw",
            "is_primary",
        )
        read_only_fields = fields

    def _resolve_autodb_payload(self, obj: GarageVehicle) -> dict[str, Any]:
        if obj.catalog_source != GarageVehicle.CATALOG_SOURCE_AUTODB_PRO or obj.autodb_passanger_car_id is None:
            return {}

        cache = self.context.setdefault("_autodb_payload_cache", {})
        cache_key = int(obj.autodb_passanger_car_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        passanger_car = get_passanger_car(passanger_car_id=cache_key) or {}
        manufacturer = get_vehicle_manufacturer(obj.autodb_manufacturer_id) if obj.autodb_manufacturer_id is not None else {}
        model = (
            get_vehicle_model(manufacturer_id=obj.autodb_manufacturer_id, model_id=obj.autodb_model_id)
            if obj.autodb_manufacturer_id is not None and obj.autodb_model_id is not None
            else {}
        )
        resolved = {
            "manufacturer_name": _clean_text((manufacturer or {}).get("name") or ""),
            "model_name": _clean_text((model or {}).get("description") or (model or {}).get("name") or ""),
            "passanger_name": _clean_text(passanger_car.get("name") or passanger_car.get("description") or ""),
            "passanger_description": _clean_text(passanger_car.get("description") or ""),
            "year_from": passanger_car.get("year_from"),
            "year_to": passanger_car.get("year_to"),
        }
        cache[cache_key] = resolved
        return resolved

    def get_brand(self, obj: GarageVehicle) -> str:
        if obj.catalog_source == GarageVehicle.CATALOG_SOURCE_AUTODB_PRO:
            return self._resolve_autodb_payload(obj).get("manufacturer_name", "")
        if obj.car_modification and obj.car_modification.make:
            return _clean_text(obj.car_modification.make.name)
        return ""

    def get_model(self, obj: GarageVehicle) -> str:
        if obj.catalog_source == GarageVehicle.CATALOG_SOURCE_AUTODB_PRO:
            return self._resolve_autodb_payload(obj).get("model_name", "")
        if obj.car_modification and obj.car_modification.model:
            return _clean_text(obj.car_modification.model.name)
        return ""

    def get_year(self, obj: GarageVehicle) -> int | None:
        if obj.catalog_source == GarageVehicle.CATALOG_SOURCE_AUTODB_PRO:
            if isinstance(obj.year, int):
                return obj.year
            payload = self._resolve_autodb_payload(obj)
            year_from = payload.get("year_from")
            return int(year_from) if isinstance(year_from, int) else obj.year

        if obj.car_modification is not None:
            return obj.car_modification.year
        return obj.year

    def get_modification(self, obj: GarageVehicle) -> str:
        if obj.catalog_source == GarageVehicle.CATALOG_SOURCE_AUTODB_PRO:
            if obj.autodb_modification:
                return _clean_text(obj.autodb_modification)
            payload = self._resolve_autodb_payload(obj)
            return payload.get("passanger_description", "") or payload.get("passanger_name", "")
        return _clean_text(getattr(obj.car_modification, "modification", "") if obj.car_modification else "")

    def get_period(self, obj: GarageVehicle) -> str:
        if obj.catalog_source == GarageVehicle.CATALOG_SOURCE_AUTODB_PRO:
            payload = self._resolve_autodb_payload(obj)
            year_from = payload.get("year_from")
            year_to = payload.get("year_to")
            if isinstance(year_from, int) and isinstance(year_to, int):
                if year_from == year_to:
                    return str(year_from)
                return f"{year_from}–{year_to}"
            if isinstance(year_from, int):
                return str(year_from)
            if isinstance(year_to, int):
                return str(year_to)
        return str(obj.year) if isinstance(obj.year, int) else ""

    def get_engine(self, obj: GarageVehicle) -> str:
        if obj.catalog_source == GarageVehicle.CATALOG_SOURCE_AUTODB_PRO:
            return _clean_text(obj.autodb_engine)
        return _clean_text(getattr(obj.car_modification, "engine", "") if obj.car_modification else "")

    def get_power_hp(self, obj: GarageVehicle) -> int | None:
        if obj.catalog_source == GarageVehicle.CATALOG_SOURCE_AUTODB_PRO:
            return obj.autodb_power_hp
        return getattr(obj.car_modification, "hp_from", None) if obj.car_modification else None

    def get_power_kw(self, obj: GarageVehicle) -> int | None:
        if obj.catalog_source == GarageVehicle.CATALOG_SOURCE_AUTODB_PRO:
            return obj.autodb_power_kw
        return getattr(obj.car_modification, "kw_from", None) if obj.car_modification else None

    def get_vehicle_label(self, obj: GarageVehicle) -> str:
        if obj.catalog_source == GarageVehicle.CATALOG_SOURCE_AUTODB_PRO:
            payload = self._resolve_autodb_payload(obj)
            if obj.autodb_vehicle_label:
                return _clean_text(obj.autodb_vehicle_label)

            year_from = payload.get("year_from")
            year_to = payload.get("year_to")
            year_label = ""
            if isinstance(year_from, int) and isinstance(year_to, int):
                year_label = f"{year_from}-{year_to}"
            elif isinstance(year_from, int):
                year_label = str(year_from)

            return _clean_text(
                ", ".join(
                    part
                    for part in [
                        " ".join(
                            part
                            for part in [
                                payload.get("manufacturer_name", ""),
                                payload.get("model_name", ""),
                                payload.get("passanger_name", ""),
                            ]
                            if part
                        ),
                        year_label,
                    ]
                    if part
                )
            )

        title = " ".join(
            part
            for part in [
                _clean_text(getattr(getattr(obj.car_modification, "make", None), "name", "") if obj.car_modification else ""),
                _clean_text(getattr(getattr(obj.car_modification, "model", None), "name", "") if obj.car_modification else ""),
                str(obj.car_modification.year) if obj.car_modification and obj.car_modification.year else "",
            ]
            if part
        )
        subtitle = _clean_text(getattr(obj.car_modification, "modification", "") if obj.car_modification else "")
        return _clean_text(" - ".join(part for part in [title, subtitle] if part))
