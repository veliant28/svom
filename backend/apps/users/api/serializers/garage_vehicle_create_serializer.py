from django.db import IntegrityError, transaction
from rest_framework import serializers

from apps.autocatalog.models import CarModification
from apps.users.models import GarageVehicle


class GarageVehicleCreateSerializer(serializers.ModelSerializer):
    car_modification = serializers.PrimaryKeyRelatedField(
        queryset=CarModification.objects.select_related("make", "model"),
        required=True,
    )

    class Meta:
        model = GarageVehicle
        fields = ("car_modification", "is_primary")
        validators = []

    def validate(self, attrs):
        request = self.context["request"]
        attrs["user"] = request.user

        car_modification = attrs["car_modification"]
        attrs["make"] = None
        attrs["model"] = None
        attrs["generation"] = None
        attrs["engine"] = None
        attrs["modification"] = None
        attrs["nickname"] = ""
        attrs["vin"] = ""
        attrs["year"] = car_modification.year
        return attrs

    def create(self, validated_data):
        user = validated_data["user"]
        car_modification = validated_data["car_modification"]
        is_primary = validated_data.get("is_primary", False)
        expected_year = car_modification.year

        with transaction.atomic():
            if is_primary:
                (
                    GarageVehicle.objects.filter(user=user, is_primary=True)
                    .exclude(car_modification=car_modification)
                    .update(is_primary=False)
                )

            existing = GarageVehicle.objects.filter(
                user=user,
                car_modification=car_modification,
            ).first()
            if existing is not None:
                update_fields: list[str] = []
                if existing.year != expected_year:
                    existing.year = expected_year
                    update_fields.append("year")
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
                return GarageVehicle.objects.get(user=user, car_modification=car_modification)
