from django.db import router
from django.test import SimpleTestCase

from apps.autodb.db_router import AutoDbRouter
from apps.autodb.models import AutoDbEngine, AutoDbVehicleManufacturer


class AutoDbRouterTests(SimpleTestCase):
    def test_autodb_models_use_auto_db_pro_alias(self):
        self.assertEqual(router.db_for_read(AutoDbVehicleManufacturer), "auto_db_pro")
        self.assertEqual(router.db_for_write(AutoDbEngine), "auto_db_pro")

    def test_router_blocks_autodb_migrations_on_default(self):
        db_router = AutoDbRouter()
        self.assertFalse(db_router.allow_migrate("default", "autodb"))
        self.assertTrue(db_router.allow_migrate("auto_db_pro", "autodb"))
        self.assertFalse(db_router.allow_migrate("auto_db_pro", "catalog"))
