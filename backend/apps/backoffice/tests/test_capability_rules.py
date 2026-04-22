from django.test import SimpleTestCase

from apps.backoffice.permissions.capability_rules import resolve_required_capabilities_for_request


class BackofficeCapabilityRulesTest(SimpleTestCase):
    def test_schedule_endpoint_requires_schedule_capability(self):
        capabilities = resolve_required_capabilities_for_request(
            "/api/backoffice/import-schedules/",
            "GET",
        )
        self.assertEqual(capabilities, ("schedules.view",))

    def test_loyalty_endpoint_is_available_for_loyalty_capability(self):
        capabilities = resolve_required_capabilities_for_request(
            "/api/backoffice/loyalty/issue/",
            "POST",
        )
        self.assertEqual(capabilities, ("loyalty.issue",))

    def test_admin_only_endpoints_have_dedicated_capabilities(self):
        self.assertEqual(
            resolve_required_capabilities_for_request("/api/backoffice/payments/", "GET"),
            ("payments.view",),
        )
        self.assertEqual(
            resolve_required_capabilities_for_request("/api/backoffice/nova-poshta/senders/", "GET"),
            ("nova_poshta.settings",),
        )
        self.assertEqual(
            resolve_required_capabilities_for_request("/api/backoffice/brands/", "GET"),
            ("brands.view",),
        )
        self.assertEqual(
            resolve_required_capabilities_for_request("/api/backoffice/categories/", "GET"),
            ("categories.view",),
        )
        self.assertEqual(
            resolve_required_capabilities_for_request("/api/backoffice/autocatalog/", "GET"),
            ("autocatalog.view",),
        )
