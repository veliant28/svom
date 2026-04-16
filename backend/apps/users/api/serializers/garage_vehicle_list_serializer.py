from rest_framework import serializers

from apps.users.models import GarageVehicle


class GarageVehicleListSerializer(serializers.ModelSerializer):
    car_modification_id = serializers.IntegerField(read_only=True, allow_null=True)
    brand = serializers.CharField(source="car_modification.make.name", read_only=True, default="")
    model = serializers.CharField(source="car_modification.model.name", read_only=True, default="")
    year = serializers.IntegerField(source="car_modification.year", read_only=True, allow_null=True, default=None)
    modification = serializers.CharField(source="car_modification.modification", read_only=True, default="")
    engine = serializers.CharField(source="car_modification.engine", read_only=True, default="")
    power_hp = serializers.IntegerField(source="car_modification.hp_from", read_only=True, allow_null=True, default=None)
    power_kw = serializers.IntegerField(source="car_modification.kw_from", read_only=True, allow_null=True, default=None)

    class Meta:
        model = GarageVehicle
        fields = (
            "id",
            "user",
            "car_modification_id",
            "brand",
            "model",
            "year",
            "modification",
            "engine",
            "power_hp",
            "power_kw",
            "is_primary",
        )
        read_only_fields = fields
