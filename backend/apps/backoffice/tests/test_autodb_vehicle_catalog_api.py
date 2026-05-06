from __future__ import annotations

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.users.models import User


class BackofficeAutoDbVehicleCatalogAPITests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="autodb-staff@test.local",
            first_name="autodb",
            password="demo12345",
            is_staff=True,
            is_superuser=True,
        )
        self.token = Token.objects.create(user=self.staff)

    def _auth(self) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

    @patch("apps.backoffice.api.views.autodb_vehicle_catalog_views.list_admin_vehicle_catalog")
    def test_endpoint_returns_paginated_rows(self, selector_mock):
        selector_mock.return_value = {
            "count": 1,
            "results": [
                {
                    "passanger_car_id": 3724,
                    "manufacturer_id": 72,
                    "model_id": 82,
                    "make": "MAZDA",
                    "model": "XEDOS 6 (CA)",
                    "modification": "2.0 V6",
                    "period": "1992–1994",
                    "period_raw": "01.1992 - 05.1994",
                    "volume": "1995",
                    "engine": "KF-ZE",
                    "hp": "144",
                    "kw": "106",
                }
            ],
        }

        response = self.client.get(
            reverse("backoffice_api:autodb-vehicle-catalog"),
            {
                "manufacturer_id": "72",
                "model_id": "82",
                "year": "1992",
                "q": "XEDOS",
                "modification": "2.0 V6",
                "volume": "1995",
                "engine": "KF",
                "page": 2,
                "page_size": 50,
            },
            **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["make"], "MAZDA")
        self.assertEqual(row["period"], "1992–1994")
        selector_mock.assert_called_once()
        call_kwargs = selector_mock.call_args.kwargs
        self.assertEqual(call_kwargs["manufacturer_id"], 72)
        self.assertEqual(call_kwargs["model_id"], 82)
        self.assertEqual(call_kwargs["year"], 1992)
        self.assertEqual(call_kwargs["q"], "XEDOS")
        self.assertEqual(call_kwargs["modification"], "2.0 V6")
        self.assertEqual(call_kwargs["volume"], "1995")
        self.assertEqual(call_kwargs["engine"], "KF")
        self.assertEqual(call_kwargs["page"], 2)
        self.assertEqual(call_kwargs["page_size"], 50)

    @patch("apps.backoffice.api.views.autodb_vehicle_catalog_views.list_admin_vehicle_manufacturers")
    def test_manufacturers_endpoint(self, selector_mock):
        selector_mock.return_value = [{"id": 72, "name": "MAZDA"}, {"id": 111, "name": "TOYOTA"}]

        response = self.client.get(reverse("backoffice_api:autodb-vehicle-manufacturers"), {"q": "MAZ"}, **self._auth())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["id"], 72)
        self.assertEqual(response.data[0]["name"], "MAZDA")
        selector_mock.assert_called_once_with(q="MAZ")

    @patch("apps.backoffice.api.views.autodb_vehicle_catalog_views.list_admin_vehicle_models")
    def test_models_endpoint_filters_by_manufacturer(self, selector_mock):
        selector_mock.return_value = [{"id": 82, "manufacturer_id": 72, "name": "XEDOS 6 (CA)", "construction_interval": "1990 - 2000"}]

        response = self.client.get(
            reverse("backoffice_api:autodb-vehicle-manufacturer-models", kwargs={"manufacturer_id": 72}),
            {"q": "XEDOS"},
            **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["manufacturer_id"], 72)
        self.assertEqual(response.data[0]["name"], "XEDOS 6 (CA)")
        selector_mock.assert_called_once_with(manufacturer_id=72, q="XEDOS")

    @patch("apps.backoffice.api.views.autodb_vehicle_catalog_views.list_admin_vehicle_filter_options")
    def test_filter_options_endpoint(self, selector_mock):
        selector_mock.return_value = {
            "years": [2020, 2019],
            "manufacturers": [{"id": 72, "name": "MAZDA"}],
            "models": [{"id": 82, "manufacturer_id": 72, "name": "XEDOS 6 (CA)", "construction_interval": "1990 - 2000"}],
            "modifications": ["2.0 V6"],
            "volumes": ["1995"],
            "engines": ["KF-ZE"],
        }

        response = self.client.get(
            reverse("backoffice_api:autodb-vehicle-filter-options"),
            {
                "year": "1992",
                "manufacturer_id": "72",
                "model_id": "82",
                "modification": "2.0 V6",
                "volume": "1995",
            },
            **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["years"], [2020, 2019])
        self.assertEqual(response.data["manufacturers"][0]["name"], "MAZDA")
        self.assertEqual(response.data["engines"], ["KF-ZE"])
        selector_mock.assert_called_once_with(
            year=1992,
            manufacturer_id=72,
            model_id=82,
            modification="2.0 V6",
            volume="1995",
        )

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    @patch("apps.autodb.services.remote_client.AutoDbProRemoteClient.from_settings")
    @patch("apps.backoffice.api.views.autodb_vehicle_catalog_views.list_admin_vehicle_catalog")
    def test_endpoint_does_not_call_remote_or_utr(self, selector_mock, remote_factory, utr_client_cls):
        selector_mock.return_value = {"count": 0, "results": []}

        response = self.client.get(reverse("backoffice_api:autodb-vehicle-catalog"), **self._auth())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        remote_factory.assert_not_called()
        utr_client_cls.assert_not_called()

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    @patch("apps.autodb.services.remote_client.AutoDbProRemoteClient.from_settings")
    @patch("apps.backoffice.api.views.autodb_vehicle_catalog_views.list_admin_vehicle_manufacturers")
    def test_manufacturers_endpoint_does_not_call_remote_or_utr(self, selector_mock, remote_factory, utr_client_cls):
        selector_mock.return_value = []
        response = self.client.get(reverse("backoffice_api:autodb-vehicle-manufacturers"), **self._auth())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        remote_factory.assert_not_called()
        utr_client_cls.assert_not_called()

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    @patch("apps.autodb.services.remote_client.AutoDbProRemoteClient.from_settings")
    @patch("apps.backoffice.api.views.autodb_vehicle_catalog_views.list_admin_vehicle_models")
    def test_models_endpoint_does_not_call_remote_or_utr(self, selector_mock, remote_factory, utr_client_cls):
        selector_mock.return_value = []
        response = self.client.get(
            reverse("backoffice_api:autodb-vehicle-manufacturer-models", kwargs={"manufacturer_id": 72}),
            **self._auth(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        remote_factory.assert_not_called()
        utr_client_cls.assert_not_called()

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    @patch("apps.autodb.services.remote_client.AutoDbProRemoteClient.from_settings")
    @patch("apps.backoffice.api.views.autodb_vehicle_catalog_views.list_admin_vehicle_filter_options")
    def test_filter_options_endpoint_does_not_call_remote_or_utr(self, selector_mock, remote_factory, utr_client_cls):
        selector_mock.return_value = {
            "years": [],
            "manufacturers": [],
            "models": [],
            "modifications": [],
            "volumes": [],
            "engines": [],
        }
        response = self.client.get(reverse("backoffice_api:autodb-vehicle-filter-options"), **self._auth())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        remote_factory.assert_not_called()
        utr_client_cls.assert_not_called()
