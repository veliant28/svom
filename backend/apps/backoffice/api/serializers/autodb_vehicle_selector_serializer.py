from __future__ import annotations

from rest_framework import serializers


class BackofficeAutoDbVehicleManufacturerSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class BackofficeAutoDbVehicleModelSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    manufacturer_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    construction_interval = serializers.CharField(read_only=True)
