from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.autodb.services.raw_offer_enrichment import (
    AutoDbRawOfferEnrichmentService,
    PairBucket,
    PairResolution,
)


class AutoDbRawOfferEnrichmentServiceTests(SimpleTestCase):
    def _offer(
        self,
        *,
        brand: str,
        article: str,
        normalized_brand: str,
        normalized_article: str,
        matched_product_id: str | None = None,
        product_article: str | None = None,
        external_sku: str | None = None,
        raw_payload: dict | None = None,
        source_code: str = "",
        supplier_code: str = "",
    ):
        matched_product = SimpleNamespace(
            article=product_article if product_article is not None else article,
            normalized_brand=normalized_brand,
            brand=SimpleNamespace(name=brand),
        )
        return SimpleNamespace(
            brand_name=brand,
            article=article,
            external_sku=external_sku if external_sku is not None else article,
            normalized_brand=normalized_brand,
            normalized_article=normalized_article,
            matched_product_id=matched_product_id,
            matched_product=matched_product,
            raw_payload=raw_payload or {},
            source=SimpleNamespace(code=source_code),
            supplier=SimpleNamespace(code=supplier_code),
        )

    def test_build_pair_buckets_groups_duplicates(self):
        service = AutoDbRawOfferEnrichmentService(storage=Mock(), enrichment_service=Mock(), product_linker=Mock())
        offers = [
            self._offer(brand="AUTEX", article="820099", normalized_brand="AUTEX", normalized_article="820099", matched_product_id="p1"),
            self._offer(brand="AUTEX", article="820099", normalized_brand="AUTEX", normalized_article="820099", matched_product_id="p1"),
            self._offer(brand="AUTEX", article="820100", normalized_brand="AUTEX", normalized_article="820100", matched_product_id="p2"),
        ]

        buckets, total, failed, skipped_non_tecdoc = service.build_pair_buckets(offers=offers, tecdoc_only=False)

        self.assertEqual(total, 3)
        self.assertEqual(failed, 0)
        self.assertEqual(skipped_non_tecdoc, 0)
        self.assertEqual(len(buckets), 2)

    def test_build_pair_buckets_uses_product_article_from_db(self):
        service = AutoDbRawOfferEnrichmentService(storage=Mock(), enrichment_service=Mock(), product_linker=Mock())
        offers = [
            self._offer(
                brand="WIX FILTERS",
                article="324966",
                product_article="214082",
                external_sku="0000001",
                normalized_brand="WIXFILTERS",
                normalized_article="324966",
                source_code="gpl",
                raw_payload={"Артикул": "324966", "Артикул ТД": "WP6873", "tecdoc_article": "214082", "Код": "0000001"},
            )
        ]
        buckets, total, failed, skipped_non_tecdoc = service.build_pair_buckets(offers=offers, tecdoc_only=False)
        self.assertEqual(total, 1)
        self.assertEqual(failed, 0)
        self.assertEqual(skipped_non_tecdoc, 0)
        self.assertEqual(buckets[0].sample_article, "214082")

    @patch("apps.autodb.services.raw_offer_enrichment.Product.objects.in_bulk", return_value={})
    def test_dry_run_local_only_does_not_call_remote(self, _in_bulk):
        service = AutoDbRawOfferEnrichmentService(storage=Mock(), enrichment_service=Mock(), product_linker=Mock())
        offer = self._offer(brand="AUTEX", article="820099", normalized_brand="AUTEX", normalized_article="820099")
        local_resolution = PairResolution(
            bucket=PairBucket(
                normalized_brand="AUTEX",
                normalized_article="820099",
                sample_brand="AUTEX",
                sample_article="820099",
            ),
            source="not_found",
        )

        with (
            patch.object(service, "_resolve_local_chunk", return_value=[local_resolution]),
            patch.object(service, "_resolve_remote_chunk") as remote_chunk,
        ):
            summary = service.run(
                offers=[offer],
                dry_run=True,
                allow_remote=False,
                enrich_related=False,
                tecdoc_only=False,
                batch_size=100,
                progress_every=0,
                progress_callback=None,
            )

        remote_chunk.assert_not_called()
        self.assertEqual(summary.skipped_disabled_no_remote, 1)
        self.assertFalse(summary.remote_enabled)
        self.assertFalse(summary.remote_attempted)
        self.assertEqual(summary.remote_queries, 0)

    @patch("apps.autodb.services.raw_offer_enrichment.Product.objects.in_bulk", return_value={})
    def test_remote_called_only_for_missing_pairs(self, _in_bulk):
        service = AutoDbRawOfferEnrichmentService(storage=Mock(), enrichment_service=Mock(), product_linker=Mock())
        offers = [
            self._offer(brand="A", article="1", normalized_brand="A", normalized_article="1"),
            self._offer(brand="B", article="2", normalized_brand="B", normalized_article="2"),
        ]
        found_local = PairResolution(
            bucket=PairBucket(normalized_brand="A", normalized_article="1", sample_brand="A", sample_article="1"),
            supplier_id=300,
            canonical_article_number="1",
            article_key="300:1",
            source="local",
        )
        missing_local = PairResolution(
            bucket=PairBucket(normalized_brand="B", normalized_article="2", sample_brand="B", sample_article="2"),
            source="not_found",
        )
        missing_resolved = PairResolution(
            bucket=missing_local.bucket,
            supplier_id=301,
            canonical_article_number="2",
            article_key="301:2",
            source="remote",
        )

        with (
            patch.object(service, "_resolve_local_chunk", return_value=[found_local, missing_local]),
            patch.object(service, "_resolve_remote_chunk", return_value=[found_local, missing_resolved]) as remote_chunk,
        ):
            summary = service.run(
                offers=offers,
                dry_run=True,
                allow_remote=True,
                enrich_related=False,
                tecdoc_only=False,
                batch_size=100,
                progress_every=0,
                progress_callback=None,
            )

        remote_chunk.assert_called_once()
        self.assertEqual(summary.local_hits, 1)
        self.assertEqual(summary.remote_hits, 1)
        self.assertTrue(summary.remote_enabled)
        self.assertTrue(summary.remote_attempted)
        self.assertEqual(summary.remote_queries, 1)

    @patch("apps.autodb.services.raw_offer_enrichment.Product.objects.in_bulk", return_value={})
    def test_remote_errors_are_reported_and_disable_reason_is_set(self, _in_bulk):
        service = AutoDbRawOfferEnrichmentService(storage=Mock(), enrichment_service=Mock(), product_linker=Mock())
        offer = self._offer(brand="AUTEX", article="820099", normalized_brand="AUTEX", normalized_article="820099")
        missing_local = PairResolution(
            bucket=PairBucket(normalized_brand="AUTEX", normalized_article="820099", sample_brand="AUTEX", sample_article="820099"),
            source="not_found",
        )

        with (
            patch.object(service, "_resolve_local_chunk", return_value=[missing_local]),
            patch.object(service, "_resolve_remote_chunk", side_effect=RuntimeError("remote broken")),
        ):
            summary = service.run(
                offers=[offer],
                dry_run=False,
                allow_remote=True,
                enrich_related=False,
                tecdoc_only=False,
                batch_size=100,
                progress_every=0,
                progress_callback=None,
                remote_error_threshold=1,
            )

        self.assertTrue(summary.remote_enabled)
        self.assertTrue(summary.remote_attempted)
        self.assertEqual(summary.remote_queries, 1)
        self.assertEqual(summary.remote_errors, 1)
        self.assertEqual(summary.remote_disabled_reason, "remote_error_threshold_reached")

    @patch("apps.autodb.services.raw_offer_enrichment.Product.objects.in_bulk", return_value={})
    def test_local_resolution_is_batch_based_not_per_offer(self, _in_bulk):
        service = AutoDbRawOfferEnrichmentService(storage=Mock(), enrichment_service=Mock(), product_linker=Mock())
        offers = [
            self._offer(brand=f"B{i}", article=str(i), normalized_brand=f"B{i}", normalized_article=str(i))
            for i in range(10)
        ]

        with (
            patch.object(service, "_resolve_local_chunk", return_value=[]) as local_chunk,
            patch.object(service, "_resolve_remote_chunk", return_value=[]),
        ):
            service.run(
                offers=offers,
                dry_run=True,
                allow_remote=False,
                enrich_related=False,
                tecdoc_only=False,
                batch_size=3,
                progress_every=0,
                progress_callback=None,
            )

        self.assertEqual(local_chunk.call_count, 4)

    def test_related_enrichment_uses_table_level_calls_not_per_pair(self):
        storage = Mock()
        storage.get_remote_columns.return_value = ["supplierid", "datasupplierarticlenumber"]
        storage.fetch_remote_rows_by_composite_keys.return_value = []
        storage.upsert_rows.return_value = 0

        service = AutoDbRawOfferEnrichmentService(storage=storage, enrichment_service=Mock(), product_linker=Mock())
        resolutions = [
            PairResolution(
                bucket=PairBucket(normalized_brand="A", normalized_article="1", sample_brand="A", sample_article="1"),
                supplier_id=300,
                canonical_article_number="1",
                article_key="300:1",
            ),
            PairResolution(
                bucket=PairBucket(normalized_brand="B", normalized_article="2", sample_brand="B", sample_article="2"),
                supplier_id=301,
                canonical_article_number="2",
                article_key="301:2",
            ),
        ]

        service._bulk_related_enrichment(resolutions, persist_clone=False)

        # One get_remote_columns per table, not per pair.
        self.assertEqual(storage.get_remote_columns.call_count, len(service.RELATED_TABLES) - 1)
