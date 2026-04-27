from types import SimpleNamespace

from django.core.cache import cache
from django.test import TestCase

from apps.catalog.models import Brand, Category, Product, UtrProductEnrichment
from apps.autocatalog.services.utr_autocatalog_import_service import UtrAutocatalogImportService


class FakeUtrClient:
    def __init__(self, *, has_applicability: bool, applicability_rows: list[dict] | None = None):
        self.has_applicability = has_applicability
        self.applicability_rows = applicability_rows or []
        self.search_details_batch_calls = 0
        self.fetch_applicability_calls = 0

    def search_details_batch(self, **kwargs):
        self.search_details_batch_calls += 1
        details = kwargs.get("details") or []
        rows = [
            {
                "details": [
                    {
                        "id": item["id"],
                        "hasApplicability": self.has_applicability,
                    }
                ]
            }
            for item in details
        ]
        return SimpleNamespace(rows=rows)

    def fetch_applicability(self, **kwargs):
        self.fetch_applicability_calls += 1
        return self.applicability_rows

    def is_expired_token_error(self, exc):
        return False

    def is_circuit_open_error(self, exc):
        return False


class UtrAutocatalogImportServiceTests(TestCase):
    def tearDown(self):
        cache.clear()

    def test_import_uses_persisted_batch_search_has_applicability_flag(self):
        brand = Brand.objects.create(name="UTR Flag Brand", slug="utr-flag-brand", is_active=True)
        category = Category.objects.create(name="UTR Flag Category", slug="utr-flag-category", is_active=True)
        product = Product.objects.create(
            sku="UTR-FLAG-001",
            article="UTR-FLAG-001",
            name="UTR Flag Product",
            slug="utr-flag-product",
            brand=brand,
            category=category,
            is_active=True,
            utr_detail_id="789",
        )
        UtrProductEnrichment.objects.create(
            product=product,
            utr_detail_id="789",
            detail_payload={"id": "789", "hasApplicability": False},
        )
        client = FakeUtrClient(has_applicability=True)
        service = UtrAutocatalogImportService(client=client)

        summary = service.import_from_detail_ids(detail_ids=["789"], access_token="token")

        self.assertEqual(client.search_details_batch_calls, 0)
        self.assertEqual(client.fetch_applicability_calls, 0)
        self.assertEqual(summary.detail_ids_prefiltered_no_applicability, 1)
        self.assertTrue(service._is_detail_marked_done("789"))

    def test_import_skips_applicability_request_when_batch_search_says_no_applicability(self):
        client = FakeUtrClient(has_applicability=False)
        service = UtrAutocatalogImportService(client=client)

        summary = service.import_from_detail_ids(detail_ids=["123"], access_token="token")

        self.assertEqual(client.fetch_applicability_calls, 0)
        self.assertEqual(summary.detail_ids_processed, 0)
        self.assertEqual(summary.detail_ids_empty_applicability, 1)
        self.assertEqual(summary.detail_ids_prefiltered_no_applicability, 1)
        self.assertTrue(service._is_detail_marked_done("123"))

    def test_import_does_not_mark_suspicious_empty_applicability_as_done(self):
        client = FakeUtrClient(has_applicability=True, applicability_rows=[])
        service = UtrAutocatalogImportService(client=client)

        summary = service.import_from_detail_ids(detail_ids=["456"], access_token="token")

        self.assertEqual(client.fetch_applicability_calls, 1)
        self.assertEqual(summary.detail_ids_processed, 1)
        self.assertEqual(summary.detail_ids_empty_applicability, 1)
        self.assertEqual(summary.detail_ids_suspicious_empty_applicability, 1)
        self.assertFalse(service._is_detail_marked_done("456"))
