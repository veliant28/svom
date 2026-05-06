from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


@override_settings(AUTODB_PRO_VEHICLE_CATALOG_API_ENABLED=True)
class AutoDbVehicleCatalogAPITests(APITestCase):
    @patch("apps.autodb.api.views.vehicle_catalog_views.list_vehicle_manufacturers")
    def test_manufacturers_endpoint(self, list_manufacturers):
        list_manufacturers.return_value = [
            {"id": 72, "name": "Mazda", "description": "MAZDA", "full_description": "Mazda"}
        ]

        response = self.client.get(reverse("autodb_api:vehicle-manufacturers"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["id"], 72)

    @patch("apps.autodb.api.views.vehicle_catalog_views.list_vehicle_models")
    def test_models_endpoint(self, list_models):
        list_models.return_value = [
            {
                "id": 82,
                "manufacturer_id": 72,
                "name": "XEDOS 6 (CA)",
                "description": "XEDOS 6",
                "full_description": "XEDOS 6 (CA)",
                "construction_interval": "",
            }
        ]

        response = self.client.get(reverse("autodb_api:vehicle-models-by-manufacturer", kwargs={"manufacturer_id": 72}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["manufacturer_id"], 72)

    @patch("apps.autodb.api.views.vehicle_catalog_views.list_passanger_cars")
    def test_passanger_cars_endpoint(self, list_passanger_cars):
        list_passanger_cars.return_value = [
            {
                "id": 3724,
                "model_id": 82,
                "name": "2.0 V6",
                "description": "2.0 V6",
                "full_description": "2.0 V6",
                "construction_interval": "01.1992 - 05.1994",
                "year_from": 1992,
                "year_to": 1994,
                "raw_construction_interval": "01.1992 - 05.1994",
            }
        ]

        response = self.client.get(reverse("autodb_api:passanger-cars-by-model", kwargs={"model_id": 82}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["year_from"], 1992)

    @patch("apps.autodb.api.views.vehicle_catalog_views.list_vehicle_manufacturers")
    def test_manufacturers_endpoint_normalizes_whitespace(self, list_manufacturers):
        list_manufacturers.return_value = [
            {"id": 72, "name": "MAZDA\n  1000", "description": "MAZDA\t1000", "full_description": " MAZDA  1000 "}
        ]

        response = self.client.get(reverse("autodb_api:vehicle-manufacturers"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["name"], "MAZDA 1000")
        self.assertEqual(response.data[0]["description"], "MAZDA 1000")
        self.assertEqual(response.data[0]["full_description"], "MAZDA 1000")

    @patch("apps.autodb.api.views.vehicle_catalog_views.list_admin_vehicle_filter_options")
    def test_filter_options_endpoint(self, selector_mock):
        selector_mock.return_value = {
            "years": [2018, 2017],
            "manufacturers": [{"id": 121, "name": "VW"}],
            "models": [{"id": 1994, "name": "GOLF IV (1J1)"}],
            "modifications": ["1.4 16V"],
            "volumes": ["1390 ccm"],
            "engines": ["AHW", "AKQ"],
        }

        response = self.client.get(
            reverse("autodb_api:vehicle-filter-options"),
            {
                "year": "2000",
                "manufacturer_id": "121",
                "model_id": "1994",
                "modification": "1.4 16V",
                "volume": "1390 ccm",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["engines"], ["AHW", "AKQ"])
        selector_mock.assert_called_once_with(
            year=2000,
            manufacturer_id=121,
            model_id=1994,
            modification="1.4 16V",
            volume="1390 ccm",
            years_only=False,
        )

    @patch("apps.autodb.api.views.vehicle_catalog_views.list_admin_vehicle_filter_options")
    def test_filter_options_endpoint_years_only(self, selector_mock):
        selector_mock.return_value = {
            "years": [2026, 2025],
            "manufacturers": [],
            "models": [],
            "modifications": [],
            "volumes": [],
            "engines": [],
        }

        response = self.client.get(
            reverse("autodb_api:vehicle-filter-options"),
            {"years_only": "1"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["years"], [2026, 2025])
        selector_mock.assert_called_once_with(
            year=None,
            manufacturer_id=None,
            model_id=None,
            modification="",
            volume="",
            years_only=True,
        )

    @patch("apps.autodb.api.views.vehicle_catalog_views.list_admin_vehicle_catalog")
    def test_catalog_endpoint(self, selector_mock):
        selector_mock.return_value = {
            "count": 1,
            "results": [
                {
                    "passanger_car_id": 8799,
                    "manufacturer_id": 121,
                    "model_id": 1994,
                    "make": "VW",
                    "model": "GOLF IV (1J1)",
                    "modification": "1.4 16V",
                    "period": "1997–2005",
                    "period_raw": "08.1997 - 06.2005",
                    "volume": "1390 ccm",
                    "engine": "AHW",
                    "hp": "75 PS",
                    "kw": "55 kW",
                }
            ],
        }

        response = self.client.get(
            reverse("autodb_api:vehicle-catalog"),
            {
                "year": "2000",
                "manufacturer_id": "121",
                "model_id": "1994",
                "modification": "1.4 16V",
                "volume": "1390 ccm",
                "engine": "AHW",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["engine"], "AHW")
        selector_mock.assert_called_once()


@override_settings(AUTODB_PRO_VEHICLE_CATALOG_API_ENABLED=False)
class AutoDbVehicleCatalogAPIDisabledTests(APITestCase):
    def test_endpoint_disabled_flag(self):
        response = self.client.get(reverse("autodb_api:vehicle-manufacturers"))

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("disabled", response.data["detail"].lower())


@override_settings(AUTODB_PRO_VEHICLE_CATALOG_API_ENABLED=True)
class AutoDbVehicleCatalogAPINetworkGuardTests(APITestCase):
    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    @patch("apps.autodb.services.remote_client.AutoDbProRemoteClient.from_settings")
    @patch("apps.autodb.api.views.vehicle_catalog_views.list_vehicle_manufacturers")
    def test_endpoint_does_not_call_remote_or_utr(self, list_manufacturers, remote_factory, utr_client_cls):
        list_manufacturers.return_value = []

        response = self.client.get(reverse("autodb_api:vehicle-manufacturers"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        remote_factory.assert_not_called()
        utr_client_cls.assert_not_called()

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    @patch("apps.autodb.services.remote_client.AutoDbProRemoteClient.from_settings")
    @patch("apps.autodb.api.views.vehicle_catalog_views.list_admin_vehicle_filter_options")
    def test_filter_options_endpoint_does_not_call_remote_or_utr(self, selector_mock, remote_factory, utr_client_cls):
        selector_mock.return_value = {
            "years": [],
            "manufacturers": [],
            "models": [],
            "modifications": [],
            "volumes": [],
            "engines": [],
        }

        response = self.client.get(reverse("autodb_api:vehicle-filter-options"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        remote_factory.assert_not_called()
        utr_client_cls.assert_not_called()
