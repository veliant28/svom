from django.test import SimpleTestCase

from apps.autodb.services.clone_schema import AutoDbCloneSchemaService, RemoteColumn


class AutoDbCloneSchemaServiceTests(SimpleTestCase):
    def setUp(self):
        self.service = AutoDbCloneSchemaService(remote_client=None)  # type: ignore[arg-type]

    def test_mysql_integer_mapping(self):
        col = RemoteColumn(
            name="manufacturerid",
            data_type="int",
            column_type="int(11)",
            is_nullable=False,
            character_maximum_length=None,
            numeric_precision=11,
            numeric_scale=0,
            datetime_precision=None,
            ordinal_position=1,
        )
        self.assertEqual(self.service._mysql_type_to_pg(col), "INTEGER")

    def test_mysql_decimal_mapping(self):
        col = RemoteColumn(
            name="price",
            data_type="decimal",
            column_type="decimal(10,2)",
            is_nullable=False,
            character_maximum_length=None,
            numeric_precision=10,
            numeric_scale=2,
            datetime_precision=None,
            ordinal_position=1,
        )
        self.assertEqual(self.service._mysql_type_to_pg(col), "NUMERIC(10,2)")

    def test_mysql_varchar_mapping(self):
        col = RemoteColumn(
            name="description",
            data_type="varchar",
            column_type="varchar(255)",
            is_nullable=True,
            character_maximum_length=255,
            numeric_precision=None,
            numeric_scale=None,
            datetime_precision=None,
            ordinal_position=1,
        )
        self.assertEqual(self.service._mysql_type_to_pg(col), "VARCHAR(255)")

    def test_mysql_datetime_mapping(self):
        col = RemoteColumn(
            name="updated_at",
            data_type="datetime",
            column_type="datetime",
            is_nullable=True,
            character_maximum_length=None,
            numeric_precision=None,
            numeric_scale=None,
            datetime_precision=None,
            ordinal_position=1,
        )
        self.assertEqual(self.service._mysql_type_to_pg(col), "TIMESTAMP")

    def test_service_fields_use_prefixed_names(self):
        self.assertIn("_synced_at", self.service.SERVICE_COLUMNS)
        self.assertIn("_source_hash", self.service.SERVICE_COLUMNS)
        self.assertIn("_sync_batch_id", self.service.SERVICE_COLUMNS)
