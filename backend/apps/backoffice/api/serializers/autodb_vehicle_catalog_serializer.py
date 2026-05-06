from __future__ import annotations

from rest_framework import serializers


class BackofficeAutoDbVehicleCatalogRowSerializer(serializers.Serializer):
    passanger_car_id = serializers.IntegerField(read_only=True)
    manufacturer_id = serializers.IntegerField(read_only=True, allow_null=True)
    model_id = serializers.IntegerField(read_only=True, allow_null=True)
    make = serializers.CharField(read_only=True)
    model = serializers.CharField(read_only=True)
    modification = serializers.CharField(read_only=True)
    period = serializers.CharField(read_only=True)
    period_raw = serializers.CharField(read_only=True)
    volume = serializers.CharField(read_only=True)
    engine = serializers.CharField(read_only=True)
    hp = serializers.CharField(read_only=True)
    kw = serializers.CharField(read_only=True)

