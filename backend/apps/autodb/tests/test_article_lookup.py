from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.autodb.services.article_lookup import AutoDbArticleLookupService


class AutoDbArticleLookupServiceTests(SimpleTestCase):
    def test_supplier_resolve_uses_local_first(self):
        service = AutoDbArticleLookupService(storage=Mock())

        with (
            patch.object(service, "_find_supplier_local", return_value={"id": 12, "description": "BOSCH"}) as local_mock,
            patch.object(service, "_find_supplier_remote") as remote_mock,
        ):
            row, source, populated, remote_called = service._resolve_supplier(brand_name="Bosch", normalized_brand="BOSCH", allow_remote=True)

        self.assertEqual(row["id"], 12)
        self.assertEqual(source, "local")
        self.assertEqual(populated, {})
        self.assertFalse(remote_called)
        local_mock.assert_called_once()
        remote_mock.assert_not_called()

    def test_supplier_resolve_falls_back_to_remote_when_local_missing(self):
        storage = Mock()
        storage.upsert_rows.return_value = 0

        service = AutoDbArticleLookupService(storage=storage)
        with (
            patch.object(service, "_find_supplier_local", side_effect=[None, {"id": 77, "description": "MANN-FILTER"}]),
            patch.object(service, "_find_supplier_remote", return_value=[{"id": 77, "description": "MANN-FILTER"}]),
            patch.object(service, "_find_supplier_details_remote", return_value=[]),
        ):
            row, source, populated, remote_called = service._resolve_supplier(brand_name="MANN-FILTER", normalized_brand="MANNFILTER", allow_remote=True)

        self.assertEqual(source, "remote")
        self.assertEqual(row["id"], 77)
        self.assertEqual(populated.get("suppliers"), 1)
        self.assertTrue(remote_called)
        storage.upsert_rows.assert_called_once()

    def test_lookup_returns_not_found_without_crash(self):
        service = AutoDbArticleLookupService(storage=Mock())

        with (
            patch.object(service, "_resolve_supplier", return_value=(None, "not_found", {}, True)),
            patch.object(service, "_resolve_article", return_value=(None, "not_found", {}, True)),
        ):
            result = service.lookup(brand_name="UNKNOWN", article="NOPE")

        self.assertFalse(result.found)
        self.assertIn("supplier_not_found", result.warnings)
        self.assertIn("article_not_found", result.warnings)
        self.assertTrue(result.remote_supplier_called)
        self.assertTrue(result.remote_article_called)

    def test_lookup_uses_composite_article_key(self):
        service = AutoDbArticleLookupService(storage=Mock())

        with (
            patch.object(service, "_resolve_supplier", return_value=({"id": 300, "description": "AUTEX"}, "local", {}, False)),
            patch.object(
                service,
                "_resolve_article",
                return_value=({"supplierId": 300, "DataSupplierArticleNumber": "820099"}, "local", {}, False),
            ),
        ):
            result = service.lookup(brand_name="AUTEX", article="820099")

        self.assertTrue(result.found)
        self.assertEqual(result.article_key, "300:820099")
        self.assertNotIn("article_id_missing", result.warnings)

    def test_lookup_exposes_article_search_variants(self):
        service = AutoDbArticleLookupService(storage=Mock())

        with (
            patch.object(service, "_resolve_supplier", return_value=(None, "not_found", {}, False)),
            patch.object(service, "_resolve_article", return_value=(None, "not_found", {}, False)),
        ):
            result = service.lookup(brand_name="NGK", article="SIFR6A11")

        self.assertIn("SIFR6A-11", result.article_search_variants)

    def test_article_resolve_uses_local_first_without_remote(self):
        service = AutoDbArticleLookupService(storage=Mock())
        local_row = {"supplierid": 300, "datasupplierarticlenumber": "820099"}

        with (
            patch.object(service, "_find_article_local", return_value=local_row),
            patch.object(service, "_find_article_numbers_remote") as remote_numbers,
            patch.object(service, "_find_articles_remote") as remote_articles,
        ):
            row, source, populated, remote_called = service._resolve_article(
                supplier_id=300,
                article_raw="820099",
                normalized_article="820099",
                article_variants=("820099",),
                allow_remote=True,
            )

        self.assertEqual(source, "local")
        self.assertEqual(populated, {})
        self.assertEqual(row, local_row)
        self.assertFalse(remote_called)
        remote_numbers.assert_not_called()
        remote_articles.assert_not_called()

    def test_article_resolve_skips_remote_when_disabled(self):
        service = AutoDbArticleLookupService(storage=Mock())
        with patch.object(service, "_find_article_local", return_value=None):
            row, source, populated, remote_called = service._resolve_article(
                supplier_id=300,
                article_raw="820099",
                normalized_article="820099",
                article_variants=("820099",),
                allow_remote=False,
            )

        self.assertIsNone(row)
        self.assertEqual(source, "no_remote")
        self.assertEqual(populated, {})
        self.assertFalse(remote_called)

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    def test_lookup_does_not_call_utr(self, utr_cls):
        service = AutoDbArticleLookupService(storage=Mock())

        with (
            patch.object(service, "_resolve_supplier", return_value=(None, "not_found", {}, True)),
            patch.object(service, "_resolve_article", return_value=(None, "not_found", {}, True)),
        ):
            service.lookup(brand_name="BOSCH", article="W712/95")

        utr_cls.assert_not_called()
