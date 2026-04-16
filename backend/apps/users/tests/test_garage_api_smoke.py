from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.autocatalog.models import CarMake, CarModel, CarModification
from apps.users.models import GarageVehicle, User


class GarageAPISmokeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="garage@test.local", username="garage", password="pass12345")
        self.client.force_authenticate(user=self.user)

        self.make = CarMake.objects.create(name="BMW", slug="bmw")
        self.model = CarModel.objects.create(make=self.make, name="3 Series", slug="3-series")
        self.car_modification = CarModification.objects.create(
            make=self.make,
            model=self.model,
            year=2020,
            modification="G20 Sedan",
            engine="2.0 Turbo",
            hp_from=258,
            kw_from=190,
        )
        self.secondary_car_modification = CarModification.objects.create(
            make=self.make,
            model=self.model,
            year=2021,
            modification="G20 Touring",
            engine="2.0 Diesel",
            hp_from=190,
            kw_from=140,
        )

        self.primary_vehicle = GarageVehicle.objects.create(
            user=self.user,
            car_modification=self.car_modification,
            year=2020,
            is_primary=True,
        )

    def test_garage_endpoint_returns_authenticated_user_data(self):
        response = self.client.get(reverse("users_api:garage-vehicles"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["brand"], "BMW")
        self.assertEqual(response.data[0]["model"], "3 Series")
        self.assertEqual(response.data[0]["modification"], "G20 Sedan")
        self.assertNotIn("vin", response.data[0])

    def test_garage_create_endpoint_creates_vehicle_and_switches_primary(self):
        response = self.client.post(
            reverse("users_api:garage-vehicles"),
            {
                "car_modification": self.secondary_car_modification.id,
                "is_primary": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_vehicle_id = response.data["id"]
        self.assertTrue(
            GarageVehicle.objects.filter(
                user=self.user,
                car_modification=self.secondary_car_modification,
                id=created_vehicle_id,
            ).exists()
        )
        self.primary_vehicle.refresh_from_db()
        self.assertFalse(self.primary_vehicle.is_primary)

    def test_garage_vehicle_patch_and_delete_maintains_single_primary(self):
        secondary_vehicle = GarageVehicle.objects.create(
            user=self.user,
            car_modification=self.secondary_car_modification,
            is_primary=False,
        )

        patch_response = self.client.patch(
            reverse("users_api:garage-vehicle-detail", kwargs={"id": secondary_vehicle.id}),
            {"is_primary": True},
            format="json",
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)

        self.primary_vehicle.refresh_from_db()
        secondary_vehicle.refresh_from_db()
        self.assertFalse(self.primary_vehicle.is_primary)
        self.assertTrue(secondary_vehicle.is_primary)

        delete_response = self.client.delete(
            reverse("users_api:garage-vehicle-detail", kwargs={"id": secondary_vehicle.id})
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        self.primary_vehicle.refresh_from_db()
        self.assertTrue(self.primary_vehicle.is_primary)
