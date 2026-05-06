from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from apps.autocatalog.models import CarMake, CarModel, CarModification
from apps.users.models import GarageVehicle, User


class GarageAPISmokeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="garage@test.local", first_name="garage", password="pass12345")
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
        self.assertEqual(response.data[0]["period"], "2020")
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

    @patch("apps.users.api.serializers.garage_vehicle_create_serializer.get_vehicle_model")
    @patch("apps.users.api.serializers.garage_vehicle_create_serializer.get_vehicle_manufacturer")
    @patch("apps.users.api.serializers.garage_vehicle_create_serializer.get_passanger_car")
    def test_garage_create_autodb_vehicle_without_fk(self, passanger_car_mock, manufacturer_mock, model_mock):
        passanger_car_mock.return_value = {
            "id": 3724,
            "model_id": 82,
            "name": "MAZDA XEDOS 6 (CA) 2.0 V6",
            "description": "2.0 V6",
            "year_from": 1992,
            "year_to": 1994,
        }
        manufacturer_mock.return_value = {"id": 72, "name": "MAZDA"}
        model_mock.return_value = {"id": 82, "manufacturer_id": 72, "name": "XEDOS 6 (CA)"}

        response = self.client.post(
            reverse("users_api:garage-vehicles"),
            {
                "year": 1993,
                "autodb_manufacturer_id": 72,
                "autodb_model_id": 82,
                "autodb_passanger_car_id": 3724,
                "autodb_modification": "2.0 V6",
                "autodb_engine": "KF-ZE",
                "autodb_power_hp": 144,
                "autodb_power_kw": 106,
                "is_primary": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = GarageVehicle.objects.get(id=response.data["id"])
        self.assertEqual(created.catalog_source, GarageVehicle.CATALOG_SOURCE_AUTODB_PRO)
        self.assertIsNone(created.car_modification_id)
        self.assertEqual(created.year, 1993)
        self.assertEqual(created.autodb_passanger_car_id, 3724)
        self.assertEqual(created.autodb_modification, "2.0 V6")
        self.assertEqual(created.autodb_engine, "KF-ZE")
        self.assertEqual(created.autodb_power_hp, 144)
        self.assertEqual(created.autodb_power_kw, 106)
        self.assertTrue(created.autodb_vehicle_label)
        self.assertEqual(created.autodb_vehicle_label, "MAZDA XEDOS 6 (CA) 2.0 V6 KF-ZE, 1993")
        self.primary_vehicle.refresh_from_db()
        self.assertFalse(self.primary_vehicle.is_primary)

    @patch("apps.users.api.serializers.garage_vehicle_list_serializer.get_vehicle_model")
    @patch("apps.users.api.serializers.garage_vehicle_list_serializer.get_vehicle_manufacturer")
    @patch("apps.users.api.serializers.garage_vehicle_list_serializer.get_passanger_car")
    def test_garage_list_legacy_and_autodb_entries(self, passanger_car_mock, manufacturer_mock, model_mock):
        passanger_car_mock.return_value = {
            "id": 3724,
            "model_id": 82,
            "name": "MAZDA XEDOS 6 (CA) 2.0 V6",
            "description": "2.0 V6",
            "year_from": 1992,
            "year_to": 1994,
        }
        manufacturer_mock.return_value = {"id": 72, "name": "MAZDA"}
        model_mock.return_value = {"id": 82, "manufacturer_id": 72, "name": "XEDOS 6 (CA)"}

        GarageVehicle.objects.create(
            user=self.user,
            catalog_source=GarageVehicle.CATALOG_SOURCE_AUTODB_PRO,
            autodb_manufacturer_id=72,
            autodb_model_id=82,
            autodb_passanger_car_id=3724,
            autodb_modification="2.0 V6",
            autodb_engine="KF-ZE",
            autodb_power_hp=144,
            autodb_power_kw=106,
            year=1993,
            autodb_vehicle_label="MAZDA\\nXEDOS 6\\t2.0 V6, 1992-1994",
            is_primary=False,
        )

        response = self.client.get(reverse("users_api:garage-vehicles"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        sources = {row["catalog_source"] for row in response.data}
        self.assertIn("legacy", sources)
        self.assertIn("autodb_pro", sources)
        autodb_row = next(row for row in response.data if row["catalog_source"] == "autodb_pro")
        self.assertNotIn("\n", autodb_row["vehicle_label"])
        self.assertEqual(autodb_row["autodb_passanger_car_id"], 3724)
        self.assertEqual(autodb_row["year"], 1993)
        self.assertEqual(autodb_row["period"], "1992–1994")
        self.assertEqual(autodb_row["modification"], "2.0 V6")
        self.assertEqual(autodb_row["engine"], "KF-ZE")
        self.assertEqual(autodb_row["power_hp"], 144)
        self.assertEqual(autodb_row["power_kw"], 106)
