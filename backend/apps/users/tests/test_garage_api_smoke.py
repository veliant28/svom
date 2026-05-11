from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import GarageVehicle, User


class GarageAPISmokeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="garage@test.local", first_name="garage", password="pass12345")
        self.client.force_authenticate(user=self.user)

        self.primary_vehicle = GarageVehicle.objects.create(
            user=self.user,
            catalog_source=GarageVehicle.CATALOG_SOURCE_AUTODB_PRO,
            autodb_manufacturer_id=72,
            autodb_model_id=82,
            autodb_passanger_car_id=3723,
            autodb_modification="1.8",
            autodb_engine="FS",
            autodb_power_hp=114,
            autodb_power_kw=84,
            autodb_vehicle_label="MAZDA XEDOS 6 (CA) 1.8 FS, 1992",
            year=1992,
            is_primary=True,
        )

    @patch("apps.users.api.serializers.garage_vehicle_list_serializer.get_vehicle_model")
    @patch("apps.users.api.serializers.garage_vehicle_list_serializer.get_vehicle_manufacturer")
    @patch("apps.users.api.serializers.garage_vehicle_list_serializer.get_passanger_car")
    def test_garage_endpoint_returns_authenticated_user_data(self, passanger_car_mock, manufacturer_mock, model_mock):
        passanger_car_mock.return_value = {
            "id": 3723,
            "model_id": 82,
            "name": "MAZDA XEDOS 6 (CA) 1.8 FS",
            "description": "1.8 FS",
            "year_from": 1992,
            "year_to": 1994,
        }
        manufacturer_mock.return_value = {"id": 72, "name": "MAZDA"}
        model_mock.return_value = {"id": 82, "manufacturer_id": 72, "name": "XEDOS 6 (CA)"}

        response = self.client.get(reverse("users_api:garage-vehicles"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["catalog_source"], "autodb_pro")
        self.assertEqual(response.data[0]["brand"], "MAZDA")
        self.assertEqual(response.data[0]["model"], "XEDOS 6 (CA)")
        self.assertEqual(response.data[0]["period"], "1992–1994")
        self.assertEqual(response.data[0]["modification"], "1.8")
        self.assertNotIn("vin", response.data[0])

    @patch("apps.users.api.serializers.garage_vehicle_create_serializer.get_vehicle_model")
    @patch("apps.users.api.serializers.garage_vehicle_create_serializer.get_vehicle_manufacturer")
    @patch("apps.users.api.serializers.garage_vehicle_create_serializer.get_passanger_car")
    def test_garage_create_endpoint_creates_vehicle_and_switches_primary(self, passanger_car_mock, manufacturer_mock, model_mock):
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
        created_vehicle_id = response.data["id"]
        self.assertTrue(
            GarageVehicle.objects.filter(
                user=self.user,
                autodb_passanger_car_id=3724,
                id=created_vehicle_id,
            ).exists()
        )
        self.primary_vehicle.refresh_from_db()
        self.assertFalse(self.primary_vehicle.is_primary)

    def test_garage_vehicle_patch_and_delete_maintains_single_primary(self):
        secondary_vehicle = GarageVehicle.objects.create(
            user=self.user,
            catalog_source=GarageVehicle.CATALOG_SOURCE_AUTODB_PRO,
            autodb_manufacturer_id=72,
            autodb_model_id=82,
            autodb_passanger_car_id=3725,
            autodb_modification="2.5",
            autodb_engine="KL",
            autodb_power_hp=170,
            autodb_power_kw=125,
            autodb_vehicle_label="MAZDA XEDOS 6 (CA) 2.5 KL, 1994",
            year=1994,
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
        self.assertEqual(created.year, 1993)
        self.assertEqual(created.autodb_passanger_car_id, 3724)
        self.assertEqual(created.autodb_modification, "2.0 V6")
        self.assertEqual(created.autodb_engine, "KF-ZE")
        self.assertEqual(created.autodb_power_hp, 144)
        self.assertEqual(created.autodb_power_kw, 106)
        self.assertTrue(created.autodb_vehicle_label)
        self.assertEqual(created.autodb_vehicle_label, "MAZDA XEDOS 6 (CA) 2.0 V6 KF-ZE, 1993")

    @patch("apps.users.api.serializers.garage_vehicle_list_serializer.get_vehicle_model")
    @patch("apps.users.api.serializers.garage_vehicle_list_serializer.get_vehicle_manufacturer")
    @patch("apps.users.api.serializers.garage_vehicle_list_serializer.get_passanger_car")
    def test_garage_list_entries_are_autodb_only(self, passanger_car_mock, manufacturer_mock, model_mock):
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
        self.assertEqual(sources, {"autodb_pro"})
        autodb_row = next(row for row in response.data if row["autodb_passanger_car_id"] == 3724)
        self.assertNotIn("\n", autodb_row["vehicle_label"])
        self.assertEqual(autodb_row["year"], 1993)
        self.assertEqual(autodb_row["period"], "1992–1994")
        self.assertEqual(autodb_row["modification"], "2.0 V6")
        self.assertEqual(autodb_row["engine"], "KF-ZE")
        self.assertEqual(autodb_row["power_hp"], 144)
        self.assertEqual(autodb_row["power_kw"], 106)
