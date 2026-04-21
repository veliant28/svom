from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.users.models import User
from apps.vehicles.models import (
    VehicleEngine,
    VehicleGeneration,
    VehicleMake,
    VehicleModel,
    VehicleModification,
)


class BackofficeVehicleTaxonomyAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="vehicles-ops@test.local",
            first_name="vehicles-ops",
            password="demo12345",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            email="vehicles-customer@test.local",
            first_name="vehicles-customer",
            password="demo12345",
            is_staff=False,
        )
        self.staff_token = Token.objects.create(user=self.staff_user)
        self.regular_token = Token.objects.create(user=self.regular_user)

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
            body_type="sedan",
            transmission="at",
            drivetrain="fwd",
            year_start=2019,
            is_active=True,
        )

    def _auth(self, token: str) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_staff_can_list_vehicle_taxonomy_endpoints(self):
        makes = self.client.get(reverse("backoffice_api:vehicle-make-list-create"), **self._auth(self.staff_token.key))
        models = self.client.get(reverse("backoffice_api:vehicle-model-list-create"), **self._auth(self.staff_token.key))
        generations = self.client.get(reverse("backoffice_api:vehicle-generation-list-create"), **self._auth(self.staff_token.key))
        engines = self.client.get(reverse("backoffice_api:vehicle-engine-list-create"), **self._auth(self.staff_token.key))
        modifications = self.client.get(reverse("backoffice_api:vehicle-modification-list-create"), **self._auth(self.staff_token.key))

        self.assertEqual(makes.status_code, status.HTTP_200_OK)
        self.assertEqual(models.status_code, status.HTTP_200_OK)
        self.assertEqual(generations.status_code, status.HTTP_200_OK)
        self.assertEqual(engines.status_code, status.HTTP_200_OK)
        self.assertEqual(modifications.status_code, status.HTTP_200_OK)

        self.assertEqual(makes.data["count"], 1)
        self.assertEqual(models.data["count"], 1)
        self.assertEqual(generations.data["count"], 1)
        self.assertEqual(engines.data["count"], 1)
        self.assertEqual(modifications.data["count"], 1)

    def test_staff_can_create_update_and_delete_vehicle_make(self):
        create_response = self.client.post(
            reverse("backoffice_api:vehicle-make-list-create"),
            {
                "name": "Honda",
                "slug": "",
                "is_active": True,
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        make_id = create_response.data["id"]
        self.assertTrue(create_response.data["slug"].startswith("honda"))

        update_response = self.client.patch(
            reverse("backoffice_api:vehicle-make-update", kwargs={"id": make_id}),
            {"is_active": False},
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertFalse(update_response.data["is_active"])

        delete_response = self.client.delete(
            reverse("backoffice_api:vehicle-make-update", kwargs={"id": make_id}),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_staff_can_create_modification_and_filter_by_make(self):
        create_response = self.client.post(
            reverse("backoffice_api:vehicle-modification-list-create"),
            {
                "engine": str(self.engine.id),
                "name": "Wagon",
                "body_type": "wagon",
                "transmission": "at",
                "drivetrain": "awd",
                "year_start": 2020,
                "year_end": 2024,
                "is_active": True,
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        filtered = self.client.get(
            reverse("backoffice_api:vehicle-modification-list-create"),
            {"make": str(self.make.id), "q": "wagon"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data["count"], 1)

    def test_non_staff_user_is_forbidden(self):
        response = self.client.get(
            reverse("backoffice_api:vehicle-make-list-create"),
            **self._auth(self.regular_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
