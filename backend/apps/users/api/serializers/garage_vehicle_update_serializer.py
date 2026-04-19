from django.db import transaction
from rest_framework import serializers

from apps.users.models import GarageVehicle


class GarageVehicleUpdateSerializer(serializers.ModelSerializer):
    def update(self, instance, validated_data):
        is_primary = validated_data.get("is_primary")

        with transaction.atomic():
            if is_primary is True:
                (
                    GarageVehicle.objects.filter(user=instance.user, is_primary=True)
                    .exclude(pk=instance.pk)
                    .update(is_primary=False)
                )

            return super().update(instance, validated_data)

    class Meta:
        model = GarageVehicle
        fields = ("is_primary",)
