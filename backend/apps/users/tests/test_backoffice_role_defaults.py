from django.test import SimpleTestCase

from apps.users.rbac.roles import SYSTEM_ROLE_DEFINITIONS


class BackofficeRoleDefaultsTest(SimpleTestCase):
    def test_administrator_has_all_requested_capabilities(self):
        administrator = SYSTEM_ROLE_DEFINITIONS["administrator"]
        capabilities = set(administrator.capability_codes)
        self.assertIn("schedules.view", capabilities)
        self.assertIn("payments.view", capabilities)
        self.assertIn("nova_poshta.settings", capabilities)
        self.assertIn("brands.view", capabilities)
        self.assertIn("categories.view", capabilities)
        self.assertIn("autocatalog.view", capabilities)
        self.assertIn("loyalty.issue", capabilities)

    def test_manager_defaults_include_loyalty_and_autocatalog_only(self):
        manager = SYSTEM_ROLE_DEFINITIONS["manager"]
        capabilities = set(manager.capability_codes)
        self.assertIn("loyalty.issue", capabilities)
        self.assertIn("autocatalog.view", capabilities)
        self.assertNotIn("schedules.view", capabilities)
        self.assertNotIn("payments.view", capabilities)
        self.assertNotIn("nova_poshta.settings", capabilities)
        self.assertNotIn("brands.view", capabilities)
        self.assertNotIn("categories.view", capabilities)

    def test_operator_defaults_include_loyalty_and_autocatalog_only(self):
        operator = SYSTEM_ROLE_DEFINITIONS["operator"]
        capabilities = set(operator.capability_codes)
        self.assertIn("loyalty.issue", capabilities)
        self.assertIn("autocatalog.view", capabilities)
        self.assertNotIn("schedules.view", capabilities)
        self.assertNotIn("payments.view", capabilities)
        self.assertNotIn("nova_poshta.settings", capabilities)
        self.assertNotIn("brands.view", capabilities)
        self.assertNotIn("categories.view", capabilities)
