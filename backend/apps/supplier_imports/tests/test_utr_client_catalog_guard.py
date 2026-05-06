from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError
from apps.supplier_imports.services.integrations.utr_client import UtrClient


@override_settings(UTR_CATALOG_ENRICHMENT_ENABLED=False)
class UtrClientCatalogGuardTests(SimpleTestCase):
    @patch("apps.supplier_imports.services.integrations.utr.endpoints.catalog.fetch_detail")
    def test_catalog_detail_call_is_blocked(self, fetch_detail_mock):
        client = UtrClient()
        with self.assertRaisesMessage(SupplierClientError, "UTR catalog enrichment is disabled."):
            client.fetch_detail(access_token="token", detail_id="123")
        fetch_detail_mock.assert_not_called()

    @patch("apps.supplier_imports.services.integrations.utr.endpoints.pricelists.get_pricelist_export_params")
    def test_pricelist_endpoint_stays_enabled(self, params_mock):
        params_mock.return_value = {"ok": True}
        client = UtrClient()

        result = client.get_pricelist_export_params(access_token="token")

        self.assertEqual(result, {"ok": True})
        params_mock.assert_called_once()
