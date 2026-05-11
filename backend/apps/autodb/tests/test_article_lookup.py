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

    def test_supplier_resolve_rejects_remote_rows_without_safe_match(self):
        storage = Mock()
        storage.upsert_rows.return_value = 0

        service = AutoDbArticleLookupService(storage=storage)
        with (
            patch.object(service, "_find_supplier_local", return_value=None),
            patch.object(service, "_find_supplier_remote", return_value=[{"id": 3, "description": "ATE", "matchcode": "ATE"}]),
            patch.object(service, "_find_supplier_details_remote", return_value=[]),
        ):
            row, source, populated, remote_called = service._resolve_supplier(
                brand_name="AT",
                normalized_brand="AT",
                allow_remote=True,
            )

        self.assertIsNone(row)
        self.assertEqual(source, "not_found")
        self.assertEqual(populated.get("suppliers"), 1)
        self.assertTrue(remote_called)

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

    def test_pick_supplier_row_rejects_zero_score_fallback(self):
        service = AutoDbArticleLookupService(storage=Mock())

        result = service._pick_supplier_row(
            rows=[{"id": 22, "description": "WABCO", "matchcode": "WABCO"}],
            brand_name="AT",
            normalized_brand="AT",
        )

        self.assertIsNone(result)

    def test_pick_supplier_row_allows_safe_long_brand_extension(self):
        service = AutoDbArticleLookupService(storage=Mock())

        result = service._pick_supplier_row(
            rows=[{"id": 324, "description": "WIX FILTERS", "matchcode": "WIX FILTERS"}],
            brand_name="WIX",
            normalized_brand="WIX",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 324)

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

    def test_build_article_variants_keeps_original_case(self):
        service = AutoDbArticleLookupService(storage=Mock())

        variants = service._build_article_variants(
            article_raw="HU 1381 x",
            normalized_article="HU1381X",
            article_variants=("HU 1381 x",),
        )

        self.assertIn("HU 1381 x", variants)
        self.assertIn("HU 1381 X", variants)

    def test_compose_article_key_uses_canonical_article_normalization(self):
        service = AutoDbArticleLookupService(storage=Mock())

        key = service._compose_article_key(supplier_id=64, article_number="4 РК 813")

        self.assertEqual(key, "64:4PK813")
