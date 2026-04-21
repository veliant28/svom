from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.autocatalog.models import CarMake, CarModel, CarModification, UtrDetailCarMap
from apps.users.models import User


class BackofficeAutocatalogAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="autocatalog-ops@test.local",
            first_name="autocatalog-ops",
            password="demo12345",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            email="autocatalog-customer@test.local",
            first_name="autocatalog-customer",
            password="demo12345",
            is_staff=False,
        )
        self.staff_token = Token.objects.create(user=self.staff_user)
        self.regular_token = Token.objects.create(user=self.regular_user)

        make_audi = CarMake.objects.create(name="Audi", slug="audi")
        model_a4 = CarModel.objects.create(make=make_audi, name="A4", slug="a4")
        model_q7 = CarModel.objects.create(make=make_audi, name="Q7", slug="q7")

        make_toyota = CarMake.objects.create(name="Toyota", slug="toyota")
        model_camry = CarModel.objects.create(make=make_toyota, name="Camry", slug="camry")

        self.a4_2020 = CarModification.objects.create(
            make=make_audi,
            model=model_a4,
            year=2020,
            modification="2.0 TDI",
            capacity="1968",
            engine="TDI",
            hp_from=190,
            kw_from=140,
        )
        self.a4_2021 = CarModification.objects.create(
            make=make_audi,
            model=model_a4,
            year=2021,
            modification="2.0 TFSI quattro",
            capacity="1984",
            engine="TFSI",
            hp_from=252,
            kw_from=185,
        )
        self.camry_2018 = CarModification.objects.create(
            make=make_toyota,
            model=model_camry,
            year=2018,
            modification="2.5 Hybrid",
            capacity="2487",
            engine="A25A-FXS",
            hp_from=218,
            kw_from=160,
        )
        self.unmapped_q7 = CarModification.objects.create(
            make=make_audi,
            model=model_q7,
            year=2019,
            modification="3.0 TDI",
            capacity="2967",
            engine="TDI",
            hp_from=286,
            kw_from=210,
        )

        UtrDetailCarMap.objects.create(utr_detail_id="UTR-A4-2020", car_modification=self.a4_2020)
        UtrDetailCarMap.objects.create(utr_detail_id="UTR-A4-2021", car_modification=self.a4_2021)
        UtrDetailCarMap.objects.create(utr_detail_id="UTR-CAMRY-2018", car_modification=self.camry_2018)

    def _auth(self, token: str) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_staff_can_list_autocatalog_rows_with_required_fields_only(self):
        response = self.client.get(
            reverse("backoffice_api:autocatalog-list"),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 4)

        first_row = response.data["results"][0]
        self.assertEqual(
            set(first_row.keys()),
            {"year", "make", "model", "modification", "capacity", "engine", "hp", "kw"},
        )
        self.assertNotIn("id", first_row)
        self.assertNotIn("utr_detail_id", first_row)

        modifications = [item["modification"] for item in response.data["results"]]
        self.assertIn(self.unmapped_q7.modification, modifications)

    def test_staff_can_filter_and_search_autocatalog_rows(self):
        filtered = self.client.get(
            reverse("backoffice_api:autocatalog-list"),
            {
                "make": "Audi",
                "model": "A4",
                "year": "2021",
                "engine": "TFSI",
                "capacity": "1984",
            },
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data["count"], 1)
        self.assertEqual(filtered.data["results"][0]["modification"], self.a4_2021.modification)

        searched = self.client.get(
            reverse("backoffice_api:autocatalog-list"),
            {"q": "hybrid"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(searched.status_code, status.HTTP_200_OK)
        self.assertEqual(searched.data["count"], 1)
        self.assertEqual(searched.data["results"][0]["make"], "Toyota")

        mapped_only = self.client.get(
            reverse("backoffice_api:autocatalog-list"),
            {"mapped": "true"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(mapped_only.status_code, status.HTTP_200_OK)
        self.assertEqual(mapped_only.data["count"], 3)

    def test_non_staff_user_is_forbidden(self):
        response = self.client.get(
            reverse("backoffice_api:autocatalog-list"),
            **self._auth(self.regular_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_filter_options_are_cascaded(self):
        response = self.client.get(
            reverse("backoffice_api:autocatalog-filter-options"),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("years", response.data)
        self.assertIn("makes", response.data)
        self.assertEqual(response.data["models"], [])
        self.assertEqual(response.data["modifications"], [])
        self.assertEqual(response.data["capacities"], [])
        self.assertEqual(response.data["engines"], [])

        make_scoped = self.client.get(
            reverse("backoffice_api:autocatalog-filter-options"),
            {"make": "Audi"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(make_scoped.status_code, status.HTTP_200_OK)
        self.assertIn("A4", make_scoped.data["models"])
        self.assertEqual(make_scoped.data["modifications"], [])

        model_scoped = self.client.get(
            reverse("backoffice_api:autocatalog-filter-options"),
            {"make": "Audi", "model": "A4"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(model_scoped.status_code, status.HTTP_200_OK)
        self.assertIn("2.0 TDI", model_scoped.data["modifications"])
        self.assertEqual(model_scoped.data["capacities"], [])
        self.assertEqual(model_scoped.data["engines"], [])

        modification_scoped = self.client.get(
            reverse("backoffice_api:autocatalog-filter-options"),
            {"make": "Audi", "model": "A4", "modification": "2.0 TDI"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(modification_scoped.status_code, status.HTTP_200_OK)
        self.assertIn("1968", modification_scoped.data["capacities"])
        self.assertEqual(modification_scoped.data["engines"], [])

        capacity_scoped = self.client.get(
            reverse("backoffice_api:autocatalog-filter-options"),
            {"make": "Audi", "model": "A4", "modification": "2.0 TDI", "capacity": "1968"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(capacity_scoped.status_code, status.HTTP_200_OK)
        self.assertIn("TDI", capacity_scoped.data["engines"])
