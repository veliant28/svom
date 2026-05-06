from __future__ import annotations

import re

from rest_framework import serializers

_WS_RE = re.compile(r"[\n\r\t]+")
_MULTI_SPACE_RE = re.compile(r"\s+")


class CleanTextField(serializers.CharField):
    def to_representation(self, value):
        rendered = super().to_representation(value)
        normalized = _WS_RE.sub(" ", str(rendered or ""))
        normalized = _MULTI_SPACE_RE.sub(" ", normalized)
        return normalized.strip()


class AutoDbVehicleManufacturerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = CleanTextField()
    description = CleanTextField(allow_blank=True)
    full_description = CleanTextField(allow_blank=True)


class AutoDbVehicleModelSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    manufacturer_id = serializers.IntegerField()
    name = CleanTextField()
    description = CleanTextField(allow_blank=True)
    full_description = CleanTextField(allow_blank=True)
    construction_interval = CleanTextField(allow_blank=True, required=False)


class AutoDbPassangerCarSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    model_id = serializers.IntegerField()
    name = CleanTextField()
    description = CleanTextField(allow_blank=True)
    full_description = CleanTextField(allow_blank=True)
    construction_interval = CleanTextField(allow_blank=True)
    year_from = serializers.IntegerField(allow_null=True)
    year_to = serializers.IntegerField(allow_null=True)
    raw_construction_interval = CleanTextField(allow_blank=True)


class AutoDbPassangerCarAttributeSerializer(serializers.Serializer):
    title = CleanTextField(allow_blank=True)
    value = CleanTextField(allow_blank=True)
    type = CleanTextField(allow_blank=True)
    unit = CleanTextField(allow_blank=True)


class AutoDbVehicleSearchResponseSerializer(serializers.Serializer):
    manufacturers = AutoDbVehicleManufacturerSerializer(many=True)
    models = AutoDbVehicleModelSerializer(many=True)
    passanger_cars = AutoDbPassangerCarSerializer(many=True)


class AutoDbVehicleFilterOptionManufacturerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = CleanTextField()


class AutoDbVehicleFilterOptionModelSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = CleanTextField()


class AutoDbVehicleFilterOptionsSerializer(serializers.Serializer):
    years = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
    manufacturers = AutoDbVehicleFilterOptionManufacturerSerializer(many=True)
    models = AutoDbVehicleFilterOptionModelSerializer(many=True)
    modifications = serializers.ListField(child=CleanTextField(), allow_empty=True)
    volumes = serializers.ListField(child=CleanTextField(), allow_empty=True)
    engines = serializers.ListField(child=CleanTextField(), allow_empty=True)


class AutoDbVehicleCatalogRowSerializer(serializers.Serializer):
    passanger_car_id = serializers.IntegerField()
    manufacturer_id = serializers.IntegerField(allow_null=True)
    model_id = serializers.IntegerField(allow_null=True)
    make = CleanTextField(allow_blank=True)
    model = CleanTextField(allow_blank=True)
    modification = CleanTextField(allow_blank=True)
    period = CleanTextField(allow_blank=True)
    period_raw = CleanTextField(allow_blank=True)
    volume = CleanTextField(allow_blank=True)
    engine = CleanTextField(allow_blank=True)
    hp = CleanTextField(allow_blank=True)
    kw = CleanTextField(allow_blank=True)


class AutoDbVehicleCatalogResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = AutoDbVehicleCatalogRowSerializer(many=True)
