from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.autodb.selectors.admin_vehicle_catalog import (
    DB_ALIAS,
    format_admin_vehicle_period,
    list_admin_vehicle_catalog,
    list_admin_vehicle_filter_options,
    list_admin_vehicle_manufacturers,
    list_admin_vehicle_models,
)


class AdminVehicleCatalogSelectorTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_selector_uses_local_autodb_alias(self):
        self.assertEqual(DB_ALIAS, "auto_db_pro")

    def test_period_formatter_handles_known_patterns(self):
        self.assertEqual(format_admin_vehicle_period("01.1992 - 05.1994"), "1992–1994")
        self.assertEqual(format_admin_vehicle_period("1990 - 2000"), "1990–2000")
        self.assertEqual(format_admin_vehicle_period("01.1992 - "), "з 1992")
        self.assertEqual(format_admin_vehicle_period("- 05.1994"), "до 1994")
        self.assertEqual(format_admin_vehicle_period("n/a"), "n/a")

    @patch("apps.autodb.selectors.admin_vehicle_catalog._fetch_rows")
    @patch("apps.autodb.selectors.admin_vehicle_catalog._table_columns")
    def test_selector_reads_expected_raw_tables(self, table_columns_mock, fetch_rows_mock):
        table_columns_mock.side_effect = lambda table: {
            "models": ("id", "manufacturerid", "description", "fulldescription"),
            "manufacturers": ("id", "description", "fulldescription"),
            "passanger_cars": ("id", "modelid", "description", "fulldescription", "constructioninterval"),
            "passanger_car_engines": ("id", "engineid"),
            "engines": ("id", "description", "fulldescription", "powerhp", "powerkw"),
            "passanger_car_attributes": ("id", "displaytitle", "displayvalue"),
        }.get(table, ())
        fetch_rows_mock.side_effect = [
            [
                {
                    "passanger_car_id": 3724,
                    "constructioninterval": "01.1992 - 05.1994",
                    "manufacturer_id": 72,
                    "manufacturer_description": "MAZDA",
                    "manufacturer_fulldescription": "Mazda",
                    "model_id": 82,
                    "model_description": "XEDOS 6",
                    "model_fulldescription": "XEDOS 6 (CA)",
                    "modification_description": "2.0 V6",
                    "modification_fulldescription": "2.0 V6",
                }
            ],
            [{"passanger_car_id": 3724, "engineid": 99}],
            [{"id": 99, "description": "KF-ZE", "powerhp": 144, "powerkw": 106}],
            [{"id": 3724, "displaytitle": "Объем", "displayvalue": "1995"}],
        ]

        payload = list_admin_vehicle_catalog(page=1, page_size=25)

        self.assertEqual(payload["count"], 1)
        row = payload["results"][0]
        self.assertEqual(row["make"], "Mazda")
        self.assertEqual(row["model"], "XEDOS 6")
        self.assertEqual(row["period"], "1992–1994")
        self.assertEqual(row["volume"], "1995")
        self.assertEqual(row["engine"], "KF-ZE")
        self.assertEqual(row["hp"], "144")
        self.assertEqual(row["kw"], "106")

    @patch("apps.autodb.selectors.admin_vehicle_catalog._fetch_rows")
    @patch("apps.autodb.selectors.admin_vehicle_catalog._table_columns")
    def test_manufacturers_selector_reads_local_clone(self, table_columns_mock, fetch_rows_mock):
        table_columns_mock.side_effect = lambda table: {
            "manufacturers": ("id", "description", "fulldescription", "ispassengercar"),
        }.get(table, ())
        fetch_rows_mock.return_value = [
            {"manufacturer_id": 72, "manufacturer_description": "MAZDA", "manufacturer_fulldescription": "Mazda"},
            {"manufacturer_id": 111, "manufacturer_description": "TOYOTA", "manufacturer_fulldescription": ""},
        ]

        rows = list_admin_vehicle_manufacturers()

        self.assertEqual(rows, [{"id": 72, "name": "Mazda"}, {"id": 111, "name": "TOYOTA"}])
        called_sql = fetch_rows_mock.call_args.args[0]
        self.assertIn('LOWER(CAST(man."ispassengercar" AS text))', called_sql)

    @patch("apps.autodb.selectors.admin_vehicle_catalog._fetch_rows")
    @patch("apps.autodb.selectors.admin_vehicle_catalog._table_columns")
    def test_models_selector_filters_by_manufacturer(self, table_columns_mock, fetch_rows_mock):
        table_columns_mock.side_effect = lambda table: {
            "models": ("id", "manufacturerid", "description", "fulldescription", "constructioninterval"),
            "passanger_cars": ("id", "modelid"),
        }.get(table, ())
        fetch_rows_mock.return_value = [
            {
                "model_id": 82,
                "manufacturer_id": 72,
                "model_description": "XEDOS 6",
                "model_fulldescription": "XEDOS 6 (CA)",
                "constructioninterval": "1990 - 2000",
            }
        ]

        rows = list_admin_vehicle_models(manufacturer_id=72)

        self.assertEqual(rows[0]["manufacturer_id"], 72)
        self.assertEqual(rows[0]["name"], "XEDOS 6 (CA)")
        self.assertEqual(rows[0]["construction_interval"], "1990 - 2000")
        called_sql = fetch_rows_mock.call_args.args[0]
        self.assertIn('WHERE m."manufacturerid" = %s', called_sql)
        self.assertIn('EXISTS (SELECT 1 FROM "passanger_cars" pc WHERE pc."modelid" = m."id")', called_sql)

    @patch("apps.autodb.selectors.admin_vehicle_catalog._fetch_rows")
    @patch("apps.autodb.selectors.admin_vehicle_catalog._table_columns")
    def test_selector_does_not_emit_fake_zero_values(self, table_columns_mock, fetch_rows_mock):
        table_columns_mock.side_effect = lambda table: {
            "models": ("id", "manufacturerid", "description", "fulldescription"),
            "manufacturers": ("id", "description", "fulldescription"),
            "passanger_cars": ("id", "modelid", "description", "fulldescription", "constructioninterval"),
            "passanger_car_engines": ("id", "engineid"),
            "engines": ("id", "description", "fulldescription", "capacity", "powerhp", "powerkw"),
            "passanger_car_attributes": ("id", "displaytitle", "displayvalue"),
        }.get(table, ())
        fetch_rows_mock.side_effect = [
            [
                {
                    "passanger_car_id": 3724,
                    "constructioninterval": "01.1992 - 05.1994",
                    "manufacturer_id": 72,
                    "manufacturer_description": "MAZDA",
                    "manufacturer_fulldescription": "Mazda",
                    "model_id": 82,
                    "model_description": "XEDOS 6",
                    "model_fulldescription": "XEDOS 6 (CA)",
                    "modification_description": "2.0 V6",
                    "modification_fulldescription": "2.0 V6",
                }
            ],
            [{"passanger_car_id": 3724, "engineid": 99}],
            [{"id": 99, "description": "KF-ZE", "capacity": "0 ccm", "powerhp": 0, "powerkw": "0"}],
            [{"id": 3724, "displaytitle": "Объем", "displayvalue": "0"}],
        ]

        payload = list_admin_vehicle_catalog(page=1, page_size=25)
        row = payload["results"][0]
        self.assertEqual(row["volume"], "")
        self.assertEqual(row["hp"], "")
        self.assertEqual(row["kw"], "")

    @patch("apps.autodb.selectors.admin_vehicle_catalog._fetch_rows")
    @patch("apps.autodb.selectors.admin_vehicle_catalog._table_columns")
    def test_selector_reads_power_from_attribute_values(self, table_columns_mock, fetch_rows_mock):
        table_columns_mock.side_effect = lambda table: {
            "models": ("id", "manufacturerid", "description", "fulldescription"),
            "manufacturers": ("id", "description", "fulldescription"),
            "passanger_cars": ("id", "modelid", "description", "fulldescription", "constructioninterval"),
            "passanger_car_engines": ("id", "engineid"),
            "engines": ("id", "description"),
            "passanger_car_attributes": ("passangercarid", "displaytitle", "displayvalue"),
        }.get(table, ())
        fetch_rows_mock.side_effect = [
            [
                {
                    "passanger_car_id": 8799,
                    "constructioninterval": "08.1997 - 06.2005",
                    "manufacturer_id": 121,
                    "manufacturer_description": "VW",
                    "manufacturer_fulldescription": "VW",
                    "model_id": 1994,
                    "model_description": "GOLF IV (1J1)",
                    "model_fulldescription": "VW GOLF IV (1J1)",
                    "modification_description": "1.4 16V",
                    "modification_fulldescription": "VW GOLF IV (1J1) 1.4 16V",
                }
            ],
            [{"passanger_car_id": 8799, "engineid": 9453}],
            [{"id": 9453, "description": "VW AHW"}],
            [
                {"passangercarid": 8799, "displaytitle": "Power", "displayvalue": "75 PS"},
                {"passangercarid": 8799, "displaytitle": "Power", "displayvalue": "55 kW"},
            ],
        ]

        payload = list_admin_vehicle_catalog(
            manufacturer_id=121,
            model_id=1994,
            year=2000,
            page=1,
            page_size=25,
        )

        self.assertEqual(payload["count"], 1)
        row = payload["results"][0]
        self.assertEqual(row["engine"], "VW AHW")
        self.assertEqual(row["hp"], "75 PS")
        self.assertEqual(row["kw"], "55 kW")

    @patch("apps.autodb.selectors.admin_vehicle_catalog._fetch_rows")
    @patch("apps.autodb.selectors.admin_vehicle_catalog._table_columns")
    def test_selector_deduplicates_duplicate_passanger_car_ids(self, table_columns_mock, fetch_rows_mock):
        table_columns_mock.side_effect = lambda table: {
            "models": ("id", "manufacturerid", "description", "fulldescription"),
            "manufacturers": ("id", "description", "fulldescription"),
            "passanger_cars": ("id", "modelid", "description", "fulldescription", "constructioninterval"),
            "passanger_car_engines": ("id", "engineid"),
            "engines": ("id", "description"),
            "passanger_car_attributes": ("id", "displaytitle", "displayvalue"),
        }.get(table, ())
        fetch_rows_mock.side_effect = [
            [
                {
                    "passanger_car_id": 123324,
                    "constructioninterval": "01.1992 - 05.1994",
                    "manufacturer_id": 72,
                    "manufacturer_description": "MAZDA",
                    "manufacturer_fulldescription": "Mazda",
                    "model_id": 82,
                    "model_description": "XEDOS 6",
                    "model_fulldescription": "XEDOS 6 (CA)",
                    "modification_description": "2.0 V6",
                    "modification_fulldescription": "2.0 V6",
                },
                {
                    "passanger_car_id": 123324,
                    "constructioninterval": "01.1992 - 05.1994",
                    "manufacturer_id": 72,
                    "manufacturer_description": "MAZDA",
                    "manufacturer_fulldescription": "Mazda",
                    "model_id": 82,
                    "model_description": "XEDOS 6",
                    "model_fulldescription": "XEDOS 6 (CA)",
                    "modification_description": "2.0 V6",
                    "modification_fulldescription": "2.0 V6",
                },
            ],
            [],
            [],
        ]

        payload = list_admin_vehicle_catalog(page=1, page_size=25)

        self.assertEqual(payload["count"], 1)
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["passanger_car_id"], 123324)
        rows_sql = fetch_rows_mock.call_args_list[0].args[0]
        self.assertIn('SELECT DISTINCT ON (pc."id")', rows_sql)

    @patch("apps.autodb.selectors.admin_vehicle_catalog._fetch_rows")
    @patch("apps.autodb.selectors.admin_vehicle_catalog._table_columns")
    def test_filter_options_build_cascade_years_manufacturers_models_and_engines(self, table_columns_mock, fetch_rows_mock):
        table_columns_mock.side_effect = lambda table: {
            "models": ("id", "manufacturerid", "description", "fulldescription"),
            "manufacturers": ("id", "description", "fulldescription"),
            "passanger_cars": ("id", "modelid", "description", "fulldescription", "constructioninterval"),
            "passanger_car_engines": ("id", "engineid"),
            "engines": ("id", "description", "fulldescription", "capacity", "powerhp", "powerkw"),
            "passanger_car_attributes": ("id", "displaytitle", "displayvalue"),
        }.get(table, ())
        fetch_rows_mock.side_effect = [
            [
                {
                    "passanger_car_id": 1001,
                    "constructioninterval": "01.1992 - 05.1994",
                    "manufacturer_id": 72,
                    "manufacturer_description": "MAZDA",
                    "manufacturer_fulldescription": "Mazda",
                    "model_id": 82,
                    "model_description": "XEDOS 6",
                    "model_fulldescription": "XEDOS 6 (CA)",
                    "modification_description": "2.0 V6",
                    "modification_fulldescription": "2.0 V6",
                },
                {
                    "passanger_car_id": 1002,
                    "constructioninterval": "1993 - 1995",
                    "manufacturer_id": 72,
                    "manufacturer_description": "MAZDA",
                    "manufacturer_fulldescription": "Mazda",
                    "model_id": 82,
                    "model_description": "XEDOS 6",
                    "model_fulldescription": "XEDOS 6 (CA)",
                    "modification_description": "1.6",
                    "modification_fulldescription": "1.6",
                },
            ],
            [{"passanger_car_id": 1001, "engineid": 99}],
            [{"id": 99, "description": "KF-ZE", "capacity": "1995", "powerhp": 144, "powerkw": 106}],
            [],
        ]

        payload = list_admin_vehicle_filter_options(
            year=1992,
            manufacturer_id=72,
            model_id=82,
            modification="2.0 V6",
            volume="1995",
        )

        self.assertEqual(payload["years"], [1995, 1994, 1993, 1992])
        self.assertEqual(payload["manufacturers"], [{"id": 72, "name": "Mazda"}])
        self.assertEqual(payload["models"], [{"id": 82, "name": "XEDOS 6"}])
        self.assertEqual(payload["modifications"], ["2.0 V6"])
        self.assertEqual(payload["volumes"], ["1995"])
        self.assertEqual(payload["engines"], ["KF-ZE"])

    @patch("apps.autodb.selectors.admin_vehicle_catalog._fetch_rows")
    @patch("apps.autodb.selectors.admin_vehicle_catalog._table_columns")
    def test_catalog_applies_modification_volume_and_engine_filters(self, table_columns_mock, fetch_rows_mock):
        table_columns_mock.side_effect = lambda table: {
            "models": ("id", "manufacturerid", "description", "fulldescription"),
            "manufacturers": ("id", "description", "fulldescription"),
            "passanger_cars": ("id", "modelid", "description", "fulldescription", "constructioninterval"),
            "passanger_car_engines": ("id", "engineid"),
            "engines": ("id", "description", "capacity", "powerhp", "powerkw"),
            "passanger_car_attributes": ("id", "displaytitle", "displayvalue"),
        }.get(table, ())
        fetch_rows_mock.side_effect = [
            [
                {
                    "passanger_car_id": 1001,
                    "constructioninterval": "01.1992 - 05.1994",
                    "manufacturer_id": 72,
                    "manufacturer_description": "MAZDA",
                    "manufacturer_fulldescription": "Mazda",
                    "model_id": 82,
                    "model_description": "XEDOS 6",
                    "model_fulldescription": "XEDOS 6 (CA)",
                    "modification_description": "2.0 V6",
                    "modification_fulldescription": "2.0 V6",
                },
                {
                    "passanger_car_id": 1002,
                    "constructioninterval": "01.1992 - 05.1994",
                    "manufacturer_id": 72,
                    "manufacturer_description": "MAZDA",
                    "manufacturer_fulldescription": "Mazda",
                    "model_id": 82,
                    "model_description": "XEDOS 6",
                    "model_fulldescription": "XEDOS 6 (CA)",
                    "modification_description": "1.6",
                    "modification_fulldescription": "1.6",
                },
            ],
            [{"passanger_car_id": 1001, "engineid": 99}, {"passanger_car_id": 1002, "engineid": 100}],
            [
                {"id": 99, "description": "KF-ZE", "capacity": "1995", "powerhp": 144, "powerkw": 106},
                {"id": 100, "description": "B6", "capacity": "1598", "powerhp": 90, "powerkw": 66},
            ],
            [],
        ]

        payload = list_admin_vehicle_catalog(
            manufacturer_id=72,
            model_id=82,
            year=1992,
            modification="2.0 V6",
            volume="1995",
            engine="KF-ZE",
            page=1,
            page_size=25,
        )

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["passanger_car_id"], 1001)

    @patch("apps.autodb.selectors.admin_vehicle_catalog._fetch_rows")
    @patch("apps.autodb.selectors.admin_vehicle_catalog._table_columns")
    def test_catalog_returns_all_engines_for_one_modification(self, table_columns_mock, fetch_rows_mock):
        table_columns_mock.side_effect = lambda table: {
            "models": ("id", "manufacturerid", "description", "fulldescription"),
            "manufacturers": ("id", "description", "fulldescription"),
            "passanger_cars": ("id", "modelid", "description", "fulldescription", "constructioninterval"),
            "passanger_car_engines": ("id", "engineid"),
            "engines": ("id", "description"),
            "passanger_car_attributes": ("id", "displaytitle", "displayvalue"),
        }.get(table, ())
        fetch_rows_mock.side_effect = [
            [
                {
                    "passanger_car_id": 8799,
                    "constructioninterval": "08.1997 - 06.2005",
                    "manufacturer_id": 121,
                    "manufacturer_description": "VW",
                    "manufacturer_fulldescription": "VW",
                    "model_id": 511,
                    "model_description": "GOLF IV (1J1)",
                    "model_fulldescription": "GOLF IV (1J1)",
                    "modification_description": "1.4 16V",
                    "modification_fulldescription": "1.4 16V",
                }
            ],
            [
                {"passanger_car_id": 8799, "engineid": 11},
                {"passanger_car_id": 8799, "engineid": 12},
                {"passanger_car_id": 8799, "engineid": 11},
            ],
            [
                {"id": 11, "description": "VW AHW"},
                {"id": 12, "description": "VW AKQ"},
            ],
            [],
        ]

        payload = list_admin_vehicle_catalog(
            manufacturer_id=121,
            model_id=511,
            year=2000,
            modification="1.4 16V",
            page=1,
            page_size=25,
        )

        self.assertEqual(payload["count"], 2)
        self.assertEqual([row["engine"] for row in payload["results"]], ["VW AHW", "VW AKQ"])
