from rest_framework import serializers

from apps.autocatalog.models import CarMake, CarModel, CarModification


class AutocatalogGarageMakeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarMake
        fields = ("id", "name", "slug")


class AutocatalogGarageModelSerializer(serializers.ModelSerializer):
    make_name = serializers.CharField(source="make.name", read_only=True)

    class Meta:
        model = CarModel
        fields = ("id", "name", "slug", "make", "make_name")


class AutocatalogGarageYearSerializer(serializers.Serializer):
    year = serializers.IntegerField()


class AutocatalogGarageModificationSerializer(serializers.Serializer):
    modification = serializers.CharField()


class AutocatalogGarageCapacitySerializer(serializers.Serializer):
    capacity = serializers.CharField()


class AutocatalogGarageEngineSerializer(serializers.ModelSerializer):
    brand = serializers.CharField(source="make.name", read_only=True)
    model = serializers.CharField(source="model.name", read_only=True)
    power_hp = serializers.IntegerField(source="hp_from", allow_null=True, required=False)
    power_kw = serializers.IntegerField(source="kw_from", allow_null=True, required=False)

    class Meta:
        model = CarModification
        fields = (
            "id",
            "brand",
            "model",
            "year",
            "modification",
            "engine",
            "capacity",
            "power_hp",
            "power_kw",
        )
