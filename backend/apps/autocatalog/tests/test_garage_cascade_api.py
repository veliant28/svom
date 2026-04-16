from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.autocatalog.models import CarMake, CarModel, CarModification


class GarageCascadeAPITests(APITestCase):
    def setUp(self):
        self.bmw = CarMake.objects.create(name="BMW", slug="bmw")
        self.toyota = CarMake.objects.create(name="Toyota", slug="toyota")

        self.bmw_3 = CarModel.objects.create(make=self.bmw, name="3 Series", slug="3-series")
        self.bmw_5 = CarModel.objects.create(make=self.bmw, name="5 Series", slug="5-series")
        self.toyota_camry = CarModel.objects.create(make=self.toyota, name="Camry", slug="camry")

        CarModification.objects.create(
            make=self.bmw,
            model=self.bmw_3,
            year=2020,
            modification="G20",
            capacity="2.0",
            engine="2.0 Turbo",
            hp_from=258,
            kw_from=190,
        )
        CarModification.objects.create(
            make=self.bmw,
            model=self.bmw_3,
            year=2020,
            modification="G20",
            capacity="3.0",
            engine="3.0 Turbo",
            hp_from=374,
            kw_from=275,
        )
        CarModification.objects.create(
            make=self.bmw,
            model=self.bmw_5,
            year=2021,
            modification="G30",
            capacity="2.0",
            engine="2.0 Diesel",
            hp_from=190,
            kw_from=140,
        )
        CarModification.objects.create(
            make=self.toyota,
            model=self.toyota_camry,
            year=2019,
            modification="XV70",
            capacity="2.5",
            engine="2.5",
            hp_from=181,
            kw_from=133,
        )
        CarModification.objects.create(
            make=self.toyota,
            model=self.toyota_camry,
            year=None,
            modification="Unknown",
            engine="Unknown",
        )

    def test_garage_cascade_returns_expected_data(self):
        years_response = self.client.get(reverse("autocatalog_api:garage-years"))
        self.assertEqual(years_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["year"] for item in years_response.data], [2021, 2020, 2019])

        all_makes_response = self.client.get(reverse("autocatalog_api:garage-makes"))
        self.assertEqual(all_makes_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["name"] for item in all_makes_response.data], ["BMW", "Toyota"])

        makes_response = self.client.get(
            reverse("autocatalog_api:garage-makes"),
            {"year": 2020},
        )
        self.assertEqual(makes_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["name"] for item in makes_response.data], ["BMW"])

        models_response = self.client.get(
            reverse("autocatalog_api:garage-models"),
            {"year": 2020, "make": self.bmw.id},
        )
        self.assertEqual(models_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["name"] for item in models_response.data], ["3 Series"])

        modifications_response = self.client.get(
            reverse("autocatalog_api:garage-modifications"),
            {"year": 2020, "make": self.bmw.id, "model": self.bmw_3.id},
        )
        self.assertEqual(modifications_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["modification"] for item in modifications_response.data], ["G20"])

        capacities_response = self.client.get(
            reverse("autocatalog_api:garage-capacities"),
            {"year": 2020, "make": self.bmw.id, "model": self.bmw_3.id, "modification": "G20"},
        )
        self.assertEqual(capacities_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["capacity"] for item in capacities_response.data], ["2.0", "3.0"])

        engines_response = self.client.get(
            reverse("autocatalog_api:garage-engines"),
            {"year": 2020, "make": self.bmw.id, "model": self.bmw_3.id, "modification": "G20", "capacity": "2.0"},
        )
        self.assertEqual(engines_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(engines_response.data), 1)
        self.assertEqual(engines_response.data[0]["brand"], "BMW")
        self.assertEqual(engines_response.data[0]["model"], "3 Series")
        self.assertEqual(engines_response.data[0]["engine"], "2.0 Turbo")
        self.assertIn("power_hp", engines_response.data[0])
        self.assertIn("power_kw", engines_response.data[0])
