from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from django.db import connections
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework import status

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob, AutoDbSupplier
from apps.autodb.services.link_smoke_expectations import expected_public_detail_status
from apps.autodb.services.matching import (
    AutoDbArticleSourceResolver,
    AutoDbBrandResolver,
    AutoDbCloneSyncPlanner,
    AutoDbEnrichmentPlanner,
    AutoDbLinkAuditAdapter,
    AutoDbLocalLookupService,
    AutoDbMatchJobBuilder,
    AutoDbRemoteLookupService,
    AutoDbSafeLinkPlanner,
)
from apps.autodb.services.remote_client import AutoDbProRemoteClientError
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product, ProductImage
from apps.pricing.models import Supplier, SupplierOffer


class AutoDbBrandResolverFoundationTests(SimpleTestCase):
    def _resolver(self, candidates=None):
        resolver = AutoDbBrandResolver()
        resolver._autodb_alias = Mock(return_value=None)
        resolver._supplier_import_alias = Mock(return_value="")
        resolver._supplier_candidates = Mock(return_value=candidates or [])
        return resolver

    def test_lemforder_alias_maps_to_lemforder_supplier(self):
        supplier = SimpleNamespace(supplier_id=123, supplier_name="LEMFÖRDER", supplier_matchcode="LEMFORDER", nbrofarticles=10)
        resolver = self._resolver([supplier])

        result = resolver.resolve(raw_brand="LEMFORDER", supplier_code="gpl")

        self.assertTrue(result.is_mapped)
        self.assertEqual(result.supplier_id, 123)
        self.assertEqual(result.supplier_name, "LEMFÖRDER")
        resolver._supplier_candidates.assert_called_with("LEMFORDER")

    def test_wix_alias_maps_to_wix_filters(self):
        supplier = SimpleNamespace(supplier_id=456, supplier_name="WIX FILTERS", supplier_matchcode="WIXFILTERS", nbrofarticles=10)
        resolver = self._resolver([supplier])

        result = resolver.resolve(raw_brand="WIX", supplier_code="gpl")

        self.assertTrue(result.is_mapped)
        self.assertEqual(result.supplier_id, 456)
        resolver._supplier_candidates.assert_called_with("WIXFILTERS")

    def test_ctr_duplicate_is_unsafe_ambiguous(self):
        resolver = self._resolver(
            [
                SimpleNamespace(supplier_id=1, supplier_name="CTR", supplier_matchcode="CTR", nbrofarticles=10),
                SimpleNamespace(supplier_id=2, supplier_name="CTR KOREA", supplier_matchcode="CTR", nbrofarticles=10),
            ]
        )

        result = resolver.resolve(raw_brand="CTR", supplier_code="gpl")

        self.assertEqual(result.status, AutoDbMatchJob.STATUS_SKIPPED_UNSAFE_AMBIGUOUS)
        self.assertEqual(result.decision, "unsafe_ambiguous")

    def test_non_tecdoc_brand_is_skipped(self):
        resolver = self._resolver()

        result = resolver.resolve(raw_brand="OEM", supplier_code="gpl")

        self.assertEqual(result.status, AutoDbMatchJob.STATUS_SKIPPED_NON_TECDOC)
        self.assertEqual(result.decision, "non_tecdoc")


class AutoDbBrandResolverSupplierSourceTests(TestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        with connections["auto_db_pro"].cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS suppliers (
                    id INTEGER PRIMARY KEY,
                    description TEXT NOT NULL DEFAULT '',
                    matchcode TEXT NOT NULL DEFAULT '',
                    nbrofarticles BIGINT NOT NULL DEFAULT 0
                )
                """
            )
            cursor.execute("TRUNCATE TABLE suppliers")
        AutoDbSupplier.objects.all().delete()

    def _seed_suppliers(self, rows: list[tuple[int, str, str, int]]) -> None:
        with connections["auto_db_pro"].cursor() as cursor:
            cursor.executemany(
                "INSERT INTO suppliers (id, description, matchcode, nbrofarticles) VALUES (%s, %s, %s, %s)",
                rows,
            )

    def test_resolver_uses_populated_suppliers_table(self):
        self._seed_suppliers([(101, "FEBI BILSTEIN", "FEBIBILSTEIN", 1000)])
        resolver = AutoDbBrandResolver()

        result = resolver.resolve(raw_brand="FEBI BILSTEIN", supplier_code="gpl")

        self.assertTrue(result.is_mapped)
        self.assertEqual(result.supplier_id, 101)
        self.assertEqual(result.resolver_source, "exact_supplier")

    def test_bosch_exact_resolution_from_suppliers_table(self):
        self._seed_suppliers([(77, "BOSCH", "BOSCH", 500)])
        resolver = AutoDbBrandResolver()

        result = resolver.resolve(raw_brand="BOSCH", supplier_code="gpl")

        self.assertTrue(result.is_mapped)
        self.assertEqual(result.supplier_id, 77)

    def test_wix_alias_maps_to_wix_filters_from_suppliers_table(self):
        self._seed_suppliers([(324, "WIX FILTERS", "WIXFILTERS", 900)])
        resolver = AutoDbBrandResolver()

        result = resolver.resolve(raw_brand="WIX", supplier_code="gpl")

        self.assertTrue(result.is_mapped)
        self.assertEqual(result.supplier_id, 324)
        self.assertEqual(result.resolver_source, "normalized_supplier")

    def test_missing_supplier_remains_keep_unmapped_missing_supplier(self):
        resolver = AutoDbBrandResolver()

        result = resolver.resolve(raw_brand="UNKNOWN BR", supplier_code="gpl")

        self.assertFalse(result.is_mapped)
        self.assertEqual(result.decision, "keep_unmapped_missing_supplier")

    def test_duplicate_normalized_supplier_is_unsafe_ambiguous(self):
        self._seed_suppliers(
            [
                (1001, "DUP BRAND A", "DUPBRAND", 10),
                (1002, "DUP BRAND B", "DUPBRAND", 20),
            ]
        )
        resolver = AutoDbBrandResolver()

        result = resolver.resolve(raw_brand="DUPBRAND", supplier_code="gpl")

        self.assertFalse(result.is_mapped)
        self.assertEqual(result.decision, "unsafe_ambiguous")
        self.assertEqual(result.status, AutoDbMatchJob.STATUS_SKIPPED_UNSAFE_AMBIGUOUS)

    def test_product_autodb_supplier_id_is_brand_resolved_for_matching(self):
        self._seed_suppliers([(101, "FEBI BILSTEIN", "FEBIBILSTEIN", 1000)])
        resolver = AutoDbBrandResolver()

        result = resolver.resolve(raw_brand="ANY BRAND", supplier_code="gpl", product_autodb_supplier_id=101)

        self.assertTrue(result.is_mapped)
        self.assertEqual(result.supplier_id, 101)
        self.assertEqual(result.resolver_source, "product_autodb_supplier_id")

    def test_invalid_product_autodb_supplier_id_returns_needs_review(self):
        resolver = AutoDbBrandResolver()

        result = resolver.resolve(raw_brand="ANY BRAND", supplier_code="gpl", product_autodb_supplier_id=999999)

        self.assertFalse(result.is_mapped)
        self.assertEqual(result.decision, "needs_human_approval")
        self.assertEqual(result.status, AutoDbMatchJob.STATUS_SKIPPED_UNSAFE_AMBIGUOUS)


class AutoDbArticleSourceResolverFoundationTests(SimpleTestCase):
    def setUp(self):
        self.resolver = AutoDbArticleSourceResolver()

    def test_gpl_wix_uses_payload_manufacturer_article(self):
        result = self.resolver.resolve(
            supplier_code="gpl",
            parser_type="gpl",
            raw_brand="WIX",
            raw_payload={"payload_manufacturer_article": "WL 7470", "product_article": "BAD-ARTICLE"},
            product_article="BAD-ARTICLE",
            supplier_sku="SKU-1",
        )

        self.assertTrue(result.is_usable)
        self.assertEqual(result.article_value, "WL 7470")
        self.assertEqual(result.source_type, "payload_manufacturer_article")

    def test_gpl_wix_does_not_use_product_article_when_it_differs(self):
        result = self.resolver.resolve(
            supplier_code="gpl",
            parser_type="gpl",
            raw_brand="WIX FILTERS",
            raw_payload={"product_article": "BAD-ARTICLE"},
            product_article="BAD-ARTICLE",
        )

        self.assertFalse(result.is_usable)
        self.assertEqual(result.status, "bad_article_source")

    def test_utr_wix_returns_paused_bad_article_source(self):
        result = self.resolver.resolve(parser_type="utr", raw_brand="WIX", supplier_sku="SKU-1")

        self.assertFalse(result.is_usable)
        self.assertEqual(result.source_type, "utr_wix_paused")

    def test_supplier_sku_is_not_used_blindly(self):
        result = self.resolver.resolve(supplier_code="any", raw_brand="NGK", supplier_sku="SKU-1")

        self.assertFalse(result.is_usable)
        self.assertEqual(result.source_type, "supplier_sku_not_allowed")


class FakeLocalStorage:
    def __init__(self, *, article_hit=True, linkage=True):
        self.article_hit = article_hit
        self.linkage = linkage

    def get_local_columns(self, table):
        return {
            "article_numbers": {"supplierId", "DataSupplierArticleNumber"},
            "articles": {"supplierId", "DataSupplierArticleNumber"},
            "article_prd": {"supplierId", "DataSupplierArticleNumber", "productId"},
            "prd": {"id"},
        }.get(table, set())

    def fetch_local_rows(self, *, table, filters=None, limit=100, order_by=None, columns=None):
        del limit, order_by, columns
        if table in {"article_numbers", "articles"} and self.article_hit:
            if filters.get("supplierId") == 10 and filters.get("DataSupplierArticleNumber") == "ABC123":
                return [{"DataSupplierArticleNumber": "ABC123"}]
        if table == "article_prd" and self.linkage:
            return [{"productId": 99}]
        return []

    def fetch_local_rows_in(self, *, table, column, values, extra_filters=None, limit=1000, columns=None):
        del column, extra_filters, limit, columns
        if table == "prd" and self.linkage and 99 in values:
            return [{"id": 99}]
        return []


class AutoDbMatchingDbTestCase(TestCase):
    databases = {"default"}

    def _product(self, suffix="1", *, active=True):
        brand = Brand.objects.create(name=f"Brand {suffix}", slug=f"brand-{suffix}", is_active=True)
        category = Category.objects.create(name=f"Category {suffix}", slug=f"category-{suffix}", is_active=True)
        return Product.objects.create(
            sku=f"SKU-{suffix}",
            article="ABC123",
            name=f"Product {suffix}",
            slug=f"product-{suffix}",
            brand=brand,
            category=category,
            is_active=active,
        )

    def _job(self, suffix="1", *, status_value=AutoDbMatchJob.STATUS_NEW):
        return AutoDbMatchJob.objects.create(
            product=self._product(suffix),
            supplier_code="gpl",
            raw_brand="NGK",
            normalized_brand="NGK",
            resolved_supplier_id=10,
            article_source_type="payload_manufacturer_article",
            article_value="ABC123",
            canonical_article="ABC123",
            status=status_value,
        )


class AutoDbMatchJobBuilderSupplierBindingTests(TestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        with connections["auto_db_pro"].cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS suppliers (
                    id INTEGER PRIMARY KEY,
                    description TEXT NOT NULL DEFAULT '',
                    matchcode TEXT NOT NULL DEFAULT '',
                    nbrofarticles BIGINT NOT NULL DEFAULT 0
                )
                """
            )
            cursor.execute("TRUNCATE TABLE suppliers")
            cursor.execute(
                "INSERT INTO suppliers (id, description, matchcode, nbrofarticles) VALUES (%s, %s, %s, %s)",
                [101, "FEBI BILSTEIN", "FEBIBILSTEIN", 1000],
            )
        brand = Brand.objects.create(name="FEBI BILSTEIN", slug="febi-bilstein", is_active=True)
        category = Category.objects.create(name="Suspension", slug="suspension", is_active=True)
        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.product = Product.objects.create(
            sku="FEBI-SKU-1",
            article="101000",
            name="FEBI Test Product",
            slug="febi-test-product",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=101,
            autodb_article_number="101000",
            autodb_article_key="",
        )
        self.offer = SupplierOffer.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_sku="FEBI-SUP-1",
            currency="UAH",
            purchase_price="100.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=5,
            lead_time_days=0,
            is_available=True,
            last_seen_at=timezone.now(),
        )
        self.article_resolver = Mock()
        self.article_resolver.resolve.return_value = SimpleNamespace(
            is_usable=True,
            source_type="payload_manufacturer_article",
            article_value="101000",
            canonical_article="101000",
            reason="",
            confidence=1.0,
        )

    def test_builder_uses_product_autodb_supplier_id_without_trusted_link(self):
        before_jobs = AutoDbMatchJob.objects.count()
        builder = AutoDbMatchJobBuilder(article_resolver=self.article_resolver)

        rows = builder.build_jobs(supplier_code="gpl", limit=10, dry_run=True)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.resolved_supplier_id, 101)
        self.assertEqual(row.resolver_source, "product_autodb_supplier_id")
        self.assertEqual(row.status, AutoDbMatchJob.STATUS_NEW)
        self.assertEqual(AutoDbMatchJob.objects.count(), before_jobs)

    def test_builder_excludes_trusted_linked_products(self):
        self.product.autodb_article_key = "101:101000"
        self.product.save(update_fields=["autodb_article_key", "updated_at"])
        AutoDbProductLinkQuality.objects.create(
            product=self.product,
            autodb_article_key="101:101000",
            autodb_supplier_id=101,
            autodb_article_number="101000",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="test",
            evidence={"source": "test"},
        )
        builder = AutoDbMatchJobBuilder(article_resolver=self.article_resolver)

        rows = builder.build_jobs(supplier_code="gpl", limit=10, dry_run=True)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.status, AutoDbMatchJob.STATUS_LINKED)
        self.assertEqual(row.resolver_source, "trusted_link")
        self.assertEqual(row.resolved_supplier_id, 101)

class AutoDbLocalLookupFoundationTests(AutoDbMatchingDbTestCase):
    def test_local_clone_hit_returns_local_found(self):
        job = self._job("local-hit")
        service = AutoDbLocalLookupService(storage=FakeLocalStorage(article_hit=True, linkage=True))

        result = service.lookup_job(job)

        self.assertEqual(result.status, AutoDbMatchJob.STATUS_LOCAL_FOUND)
        self.assertTrue(result.article_prd_present)
        self.assertTrue(result.prd_present)

    def test_missing_local_returns_remote_pending(self):
        job = self._job("local-miss")
        service = AutoDbLocalLookupService(storage=FakeLocalStorage(article_hit=False, linkage=True))

        result = service.lookup_job(job)

        self.assertEqual(result.status, AutoDbMatchJob.STATUS_REMOTE_PENDING)

    def test_article_prd_prd_linkage_required(self):
        job = self._job("local-linkage")
        service = AutoDbLocalLookupService(storage=FakeLocalStorage(article_hit=True, linkage=False))

        result = service.lookup_job(job)

        self.assertEqual(result.status, AutoDbMatchJob.STATUS_REMOTE_PENDING)
        self.assertIn("linkage missing", result.reason)


class AutoDbRemoteLookupFoundationTests(AutoDbMatchingDbTestCase):
    def _remote_service(self, lookup_result=None, precheck_error=None):
        remote_client = Mock()
        if precheck_error:
            remote_client.check_connection.side_effect = precheck_error
        else:
            remote_client.check_connection.return_value = True
        storage = SimpleNamespace(remote_client=remote_client, upsert_rows=Mock())
        lookup_service = SimpleNamespace(storage=storage, lookup=Mock(return_value=lookup_result))
        return AutoDbRemoteLookupService(lookup_service=lookup_service), lookup_service, storage

    def test_no_local_clone_upsert_in_read_only_mode(self):
        job = self._job("remote-readonly", status_value=AutoDbMatchJob.STATUS_REMOTE_PENDING)
        lookup_result = SimpleNamespace(
            found=True,
            supplier_id=10,
            canonical_article="ABC123",
            remote_stored_article="ABC123",
            remote_queries=3,
            matched_source="remote",
            matched_table="articles",
            local_hits=0,
            remote_hits=1,
            article_prd_rows=1,
            prd_rows=1,
            linkage_present=True,
            path="lookup_v3_readonly",
            error="",
        )
        service, lookup_service, storage = self._remote_service(lookup_result=lookup_result)

        result = service.lookup_job(job)

        self.assertEqual(result.status, AutoDbMatchJob.STATUS_REMOTE_FOUND)
        storage.upsert_rows.assert_not_called()
        lookup_service.storage.remote_client.check_connection.assert_called_once()

    def test_quota_error_maps_to_quota_paused(self):
        job = self._job("remote-quota", status_value=AutoDbMatchJob.STATUS_REMOTE_PENDING)
        service, _lookup_service, _storage = self._remote_service(
            precheck_error=AutoDbProRemoteClientError("ERROR 1226 max_questions exceeded")
        )

        result = service.lookup_job(job)

        self.assertEqual(result.status, AutoDbMatchJob.STATUS_QUOTA_PAUSED)
        job.refresh_from_db()
        self.assertEqual(job.status, AutoDbMatchJob.STATUS_QUOTA_PAUSED)

    def test_select_one_precheck_runs_before_lookup(self):
        job = self._job("remote-precheck", status_value=AutoDbMatchJob.STATUS_REMOTE_PENDING)
        lookup_result = SimpleNamespace(found=False, supplier_id=10, canonical_article="ABC123", remote_stored_article="", remote_queries=1, error="")
        service, lookup_service, _storage = self._remote_service(lookup_result=lookup_result)

        service.lookup_job(job)

        lookup_service.storage.remote_client.check_connection.assert_called_once()
        lookup_service.lookup.assert_called_once()


class AutoDbLinkAuditFoundationTests(AutoDbMatchingDbTestCase):
    def test_v3_canonical_remote_article_works_when_raw_blank_and_stock_zero_does_not_block(self):
        job = self._job("audit", status_value=AutoDbMatchJob.STATUS_REMOTE_FOUND)
        job.article_value = ""
        job.save(update_fields=["article_value", "updated_at"])
        AutoDbMatchEvidence.objects.create(
            job=job,
            stage="remote_lookup",
            source="lookup_v3_readonly",
            result=AutoDbMatchJob.STATUS_REMOTE_FOUND,
            supplier_id=10,
            article_value="",
            canonical_article="ABC123",
            remote_stored_article="ABC123",
            article_prd_present=True,
            prd_present=True,
        )

        result = AutoDbLinkAuditAdapter().audit_job(job, stock_qty=0)

        self.assertEqual(result.classification, AutoDbMatchJob.STATUS_SAFE_LINK_CANDIDATE)
        self.assertEqual(result.remote_stored_article, "ABC123")
        self.assertEqual(result.search_modes, ("deterministic_v3_canonical",))
        self.assertNotIn("fuzzy", ",".join(result.search_modes))


class AutoDbSmokeAndImageSafetyFoundationTests(AutoDbMatchingDbTestCase):
    def test_public_detail_smoke_expectation(self):
        self.assertEqual(expected_public_detail_status(is_active=False), status.HTTP_404_NOT_FOUND)
        self.assertEqual(expected_public_detail_status(is_active=True), status.HTTP_200_OK)

    def test_autodb_images_disabled_and_productimage_unchanged(self):
        job = self._job("image-safety", status_value=AutoDbMatchJob.STATUS_SAFE_LINK_CANDIDATE)
        clone_job = self._job("image-safety-clone", status_value=AutoDbMatchJob.STATUS_LOCAL_FOUND)
        ProductImage.objects.create(product=job.product, remote_url="https://example.test/a.jpg", sort_order=0)
        before = ProductImage.objects.count()

        clone_rows = AutoDbCloneSyncPlanner().plan_job(clone_job)
        safe_row = AutoDbSafeLinkPlanner().plan_job(job)
        enrich_rows = AutoDbEnrichmentPlanner().plan_job(job)

        self.assertEqual(ProductImage.objects.count(), before)
        self.assertTrue(any(row.table == "article_images" and row.action == "disabled" for row in clone_rows))
        self.assertTrue(safe_row.no_photo_overwrite)
        self.assertTrue(any(row.enrichment_type == "images" and row.action == "disabled" for row in enrich_rows))
