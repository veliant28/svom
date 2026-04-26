from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.autocatalog.models import CarMake, CarModel, CarModification


class GarageCascadeAPITests(APITestCase):
    def setUp(self):
        self.bmw = CarMake.objects.create(name="BMW", slug="bmw")
        self.toyota = CarMake.objects.create(name="Toyota", slug="toyota")
        self.vw = CarMake.objects.create(name="VW", slug="vw")
        self.honda = CarMake.objects.create(name="Honda", slug="honda")

        self.bmw_3 = CarModel.objects.create(make=self.bmw, name="3 Series", slug="3-series")
        self.bmw_5 = CarModel.objects.create(make=self.bmw, name="5 Series", slug="5-series")
        self.toyota_camry = CarModel.objects.create(make=self.toyota, name="Camry", slug="camry")
        self.vw_golf = CarModel.objects.create(make=self.vw, name="Golf", slug="golf")
        self.honda_civic = CarModel.objects.create(make=self.honda, name="Civic", slug="civic")

        CarModification.objects.create(
            make=self.bmw,
            model=self.bmw_3,
            start_date_at=date(2020, 1, 1),
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
            start_date_at=date(2020, 1, 1),
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
            start_date_at=date(2021, 1, 1),
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
            start_date_at=date(2019, 1, 1),
            end_date_at=date(2019, 12, 31),
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
        CarModification.objects.create(
            make=self.vw,
            model=self.vw_golf,
            start_date_at=date(1997, 1, 1),
            end_date_at=date(2004, 12, 31),
            year=1997,
            modification="GOLF Mk IV (1J1)",
            capacity="1.4",
            engine="AHW, AKQ, APE, AXP, BCA",
            hp_from=75,
            kw_from=55,
        )
        CarModification.objects.create(
            make=self.honda,
            model=self.honda_civic,
            start_date_at=date(2022, 1, 1),
            year=2022,
            modification="Incomplete",
            capacity="",
            engine="",
        )

    def test_garage_cascade_returns_expected_data(self):
        years_response = self.client.get(reverse("autocatalog_api:garage-years"))
        self.assertEqual(years_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["year"] for item in years_response.data],
            [2021, 2020, 2019, 2004, 2003, 2002, 2001, 2000, 1999, 1998, 1997],
        )

        all_makes_response = self.client.get(reverse("autocatalog_api:garage-makes"))
        self.assertEqual(all_makes_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["name"] for item in all_makes_response.data], [])

        makes_response = self.client.get(
            reverse("autocatalog_api:garage-makes"),
            {"year": 2020},
        )
        self.assertEqual(makes_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["name"] for item in makes_response.data], ["BMW"])

        makes_2004_response = self.client.get(
            reverse("autocatalog_api:garage-makes"),
            {"year": 2004},
        )
        self.assertEqual(makes_2004_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["name"] for item in makes_2004_response.data], ["VW"])

        makes_2005_response = self.client.get(
            reverse("autocatalog_api:garage-makes"),
            {"year": 2005},
        )
        self.assertEqual(makes_2005_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["name"] for item in makes_2005_response.data], [])

        makes_2022_response = self.client.get(
            reverse("autocatalog_api:garage-makes"),
            {"year": 2022},
        )
        self.assertEqual(makes_2022_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["name"] for item in makes_2022_response.data], [])

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
