from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.autodb.selectors import vehicle_catalog as vc


class _FakeCursor:
    description = (("value",),)

    def __init__(self):
        self.executed: list[tuple[str, list]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.executed.append((str(sql), list(params or [])))

    def fetchall(self):
        return [(1,)]


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class VehicleCatalogSelectorsTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        vc._reset_schema_cache()

    def test_fetch_rows_uses_auto_db_pro_alias(self):
        cursor = _FakeCursor()
        connection = _FakeConnection(cursor)

        with patch("apps.autodb.selectors.vehicle_catalog.connections", {"auto_db_pro": connection}):
            rows = vc._fetch_rows("SELECT 1 AS value")

        self.assertEqual(rows, [{"value": 1}])
        self.assertEqual(cursor.executed[0][0], "SELECT 1 AS value")

    def test_list_vehicle_manufacturers_filters_passanger_car(self):
        with (
            patch("apps.autodb.selectors.vehicle_catalog._table_columns", return_value=("id", "description", "fulldescription", "ispassengercar")),
            patch("apps.autodb.selectors.vehicle_catalog._fetch_rows", return_value=[{"id": 72, "description": "MAZDA", "fulldescription": "Mazda"}]) as fetch_rows,
        ):
            rows = vc.list_vehicle_manufacturers()

        self.assertEqual(rows[0]["id"], 72)
        self.assertEqual(rows[0]["name"], "Mazda")
        self.assertIn("ispassengercar", fetch_rows.call_args.args[0].lower())

    def test_list_vehicle_models_filters_by_manufacturerid(self):
        with (
            patch("apps.autodb.selectors.vehicle_catalog._table_columns", return_value=("id", "manufacturerid", "description", "fulldescription")),
            patch(
                "apps.autodb.selectors.vehicle_catalog._fetch_rows",
                return_value=[{"id": 82, "manufacturerid": 72, "description": "XEDOS 6", "fulldescription": "XEDOS 6 (CA)"}],
            ) as fetch_rows,
        ):
            rows = vc.list_vehicle_models(manufacturer_id=72)

        self.assertEqual(rows[0]["manufacturer_id"], 72)
        self.assertEqual(fetch_rows.call_args.args[1], [72])

    def test_list_passanger_cars_filters_by_modelid(self):
        with (
            patch("apps.autodb.selectors.vehicle_catalog._table_columns", return_value=("id", "modelid", "description", "fulldescription", "constructioninterval")),
            patch(
                "apps.autodb.selectors.vehicle_catalog._fetch_rows",
                return_value=[{"id": 3724, "modelid": 82, "description": "2.0 V6", "fulldescription": "2.0 V6", "constructioninterval": "01.1992 - 05.1994"}],
            ) as fetch_rows,
        ):
            rows = vc.list_passanger_cars(model_id=82)

        self.assertEqual(rows[0]["model_id"], 82)
        self.assertEqual(rows[0]["year_from"], 1992)
        self.assertEqual(fetch_rows.call_args.args[1], [82])

    def test_attributes_optional_columns_missing_is_safe(self):
        with patch("apps.autodb.selectors.vehicle_catalog._table_columns", return_value=("id", "displaytitle")):
            rows = vc.list_passanger_car_attributes(passanger_car_id=3724)

        self.assertEqual(rows, [])

    def test_passanger_car_engines_unresolved_relation_returns_empty(self):
        with patch("apps.autodb.selectors.vehicle_catalog._passanger_car_engines_link_column", return_value=None):
            rows = vc.list_passanger_car_engines(passanger_car_id=3724)

        self.assertEqual(rows, [])

    def test_passanger_car_engines_id_relation_can_be_used(self):
        with (
            patch("apps.autodb.selectors.vehicle_catalog._passanger_car_engines_link_column", return_value="id"),
            patch(
                "apps.autodb.selectors.vehicle_catalog._fetch_rows",
                side_effect=[
                    [{"engineid": 3}, {"engineid": 4}],
                    [{"id": 3, "description": "B18E"}, {"id": 4, "description": "C27A1"}],
                ],
            ),
        ):
            rows = vc.list_passanger_car_engines(passanger_car_id=3724)

        self.assertEqual(rows, [{"id": 3, "description": "B18E"}, {"id": 4, "description": "C27A1"}])
