from django.test import SimpleTestCase

from apps.autodb.services.vehicle_catalog_mappers import (
    map_country,
    map_language,
    map_manufacturer,
    map_model,
    map_passanger_car,
)


class VehicleCatalogMapperTests(SimpleTestCase):
    def test_map_country_real_shape(self):
        row = {
            "countrycode": "A",
            "currencycode": "EUR",
            "description": "Австрия",
            "isgroup": "False",
            "isocode2": "AT",
            "isocode3": "AUT",
            "isocodeno": "40",
        }
        mapped = map_country(row)

        self.assertEqual(mapped["autodb_country_id"], 40)
        self.assertEqual(mapped["name"], "Австрия")
        self.assertEqual(mapped["iso_code"], "AT")

    def test_map_language_real_shape(self):
        row = {"id": 1, "codepage": 1252, "description": "Deutsch", "isocode2": "de"}
        mapped = map_language(row)

        self.assertEqual(mapped["autodb_language_id"], 1)
        self.assertEqual(mapped["code"], "de")
        self.assertEqual(mapped["name"], "Deutsch")

    def test_map_manufacturer(self):
        row = {"id": 10, "description": "BMW", "matchcode": "BMW"}
        mapped = map_manufacturer(row)

        self.assertEqual(mapped["autodb_manufacturer_id"], 10)
        self.assertEqual(mapped["name"], "BMW")
        self.assertEqual(mapped["normalized_name"], "bmw")
        self.assertIsNone(mapped["country_id"])
        self.assertEqual(mapped["source_payload"], row)

    def test_map_model(self):
        row = {"id": 101, "manufacturerid": 10, "description": "3 Series", "constructioninterval": "01.2012 - 12.2018"}
        mapped = map_model(row)

        self.assertEqual(mapped["id"], 101)
        self.assertEqual(mapped["autodb_model_id"], 101)
        self.assertEqual(mapped["vehicle_manufacturer_id"], 10)
        self.assertEqual(mapped["name"], "3 Series")
        self.assertEqual(mapped["normalized_name"], "3 series")
        self.assertEqual(mapped["year_from"], 2012)
        self.assertEqual(mapped["year_to"], 2018)

    def test_map_passanger_car(self):
        row = {
            "id": 555,
            "manufacturerid": 10,
            "modelid": 101,
            "description": "320d",
            "constructioninterval": "01.2015 - 12.2018",
            "ktype": 123456,
        }
        mapped = map_passanger_car(row)

        self.assertEqual(mapped["id"], 555)
        self.assertEqual(mapped["autodb_vehicle_id"], 555)
        self.assertEqual(mapped["ktype"], 123456)
        self.assertEqual(mapped["vehicle_manufacturer_id"], 10)
        self.assertEqual(mapped["model_id"], 101)
        self.assertEqual(mapped["start_year"], 2015)
        self.assertEqual(mapped["end_year"], 2018)
        self.assertEqual(mapped["source_payload"], row)
