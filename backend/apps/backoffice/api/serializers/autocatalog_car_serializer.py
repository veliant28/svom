from rest_framework import serializers

from apps.autocatalog.models import CarModification


class BackofficeAutocatalogCarSerializer(serializers.ModelSerializer):
    make = serializers.CharField(source="make.name", read_only=True)
    model = serializers.CharField(source="model.name", read_only=True)
    hp = serializers.IntegerField(source="hp_from", read_only=True, allow_null=True)
    kw = serializers.IntegerField(source="kw_from", read_only=True, allow_null=True)

    class Meta:
        model = CarModification
        fields = (
            "year",
            "end_date_at",
            "make",
            "model",
            "modification",
            "capacity",
            "engine",
            "hp",
            "kw",
        )
