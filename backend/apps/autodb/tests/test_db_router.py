from django.db import router
from django.test import SimpleTestCase

from apps.autodb.db_router import AutoDbRouter
from apps.autodb.models import AutoDbEngine, AutoDbMatchJob, AutoDbRemoteSettings, AutoDbVehicleManufacturer


class AutoDbRouterTests(SimpleTestCase):
    def test_autodb_models_use_auto_db_pro_alias(self):
        self.assertEqual(router.db_for_read(AutoDbVehicleManufacturer), "auto_db_pro")
        self.assertEqual(router.db_for_write(AutoDbEngine), "auto_db_pro")

    def test_matching_state_models_use_default_alias(self):
        self.assertEqual(router.db_for_read(AutoDbMatchJob), "default")
        self.assertEqual(router.db_for_write(AutoDbMatchJob), "default")
        self.assertEqual(router.db_for_read(AutoDbRemoteSettings), "default")
        self.assertEqual(router.db_for_write(AutoDbRemoteSettings), "default")

    def test_router_splits_raw_clone_and_matching_state_migrations(self):
        db_router = AutoDbRouter()
        self.assertFalse(db_router.allow_migrate("default", "autodb", model_name="autodbvehiclemanufacturer"))
        self.assertTrue(db_router.allow_migrate("auto_db_pro", "autodb", model_name="autodbvehiclemanufacturer"))
        self.assertTrue(db_router.allow_migrate("default", "autodb", model_name="autodbmatchjob"))
        self.assertFalse(db_router.allow_migrate("auto_db_pro", "autodb", model_name="autodbmatchjob"))
        self.assertTrue(db_router.allow_migrate("default", "autodb", model_name="autodbremotesettings"))
        self.assertFalse(db_router.allow_migrate("auto_db_pro", "autodb", model_name="autodbremotesettings"))
        self.assertFalse(db_router.allow_migrate("auto_db_pro", "catalog"))
