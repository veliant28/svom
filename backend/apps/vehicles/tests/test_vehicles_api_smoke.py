from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.vehicles.models import (
    VehicleEngine,
    VehicleGeneration,
    VehicleMake,
    VehicleModel,
    VehicleModification,
)


class VehiclesAPISmokeTests(APITestCase):
    def setUp(self):
        self.make = VehicleMake.objects.create(name="Toyota", slug="toyota", is_active=True)
        self.model = VehicleModel.objects.create(make=self.make, name="Camry", slug="camry", is_active=True)
        self.generation = VehicleGeneration.objects.create(model=self.model, name="XV70", year_start=2018, is_active=True)
        self.engine = VehicleEngine.objects.create(
            generation=self.generation,
            name="2.5 Hybrid",
            code="A25A",
            fuel_type=VehicleEngine.FUEL_HYBRID,
            is_active=True,
        )
        self.modification = VehicleModification.objects.create(
            engine=self.engine,
            name="Sedan",
            year_start=2019,
            is_active=True,
        )

    def test_vehicle_hierarchy_endpoints(self):
        makes = self.client.get(reverse("vehicles_api:make-list"))
        models = self.client.get(reverse("vehicles_api:model-list"), {"make": str(self.make.id)})
        generations = self.client.get(reverse("vehicles_api:generation-list"), {"model": str(self.model.id)})
        engines = self.client.get(reverse("vehicles_api:engine-list"), {"generation": str(self.generation.id)})
        modifications = self.client.get(reverse("vehicles_api:modification-list"), {"engine": str(self.engine.id)})

        self.assertEqual(makes.status_code, status.HTTP_200_OK)
        self.assertEqual(models.status_code, status.HTTP_200_OK)
        self.assertEqual(generations.status_code, status.HTTP_200_OK)
        self.assertEqual(engines.status_code, status.HTTP_200_OK)
        self.assertEqual(modifications.status_code, status.HTTP_200_OK)

        self.assertEqual(len(models.data), 1)
        self.assertEqual(len(modifications.data), 1)
