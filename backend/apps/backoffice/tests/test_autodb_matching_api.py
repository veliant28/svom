from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import connections
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.autodb.models import AutoDbMatchJob, AutoDbRemoteQuotaState
from apps.autodb.services.matching.constants import REMOTE_QUOTA_KEY
from apps.autodb.services.matching.quota_tracker import AutoDbRemoteQuotaTracker
from apps.autodb.services.remote_client import AutoDbProRemoteClientError
from apps.catalog.models import Brand, Category, Product, ProductImage
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.users.models import User
from apps.users.rbac import set_user_system_role


class BackofficeAutoDbMatchingApiTests(APITestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        self.staff = User.objects.create_user(email="autodb-staff@test.local", password="demo12345", is_staff=True)
        self.regular = User.objects.create_user(email="autodb-user@test.local", password="demo12345", is_staff=False)
        set_user_system_role(user=self.staff, role_code="administrator")
        self.staff_token = Token.objects.create(user=self.staff)
        self.regular_token = Token.objects.create(user=self.regular)
        self.brand = Brand.objects.create(name="WIX", slug="wix", is_active=True)
        self.category = Category.objects.create(name="Filters", slug="filters", is_active=True)
        self.product = Product.objects.create(
            sku="WIX-001",
            article="WA6342",
            name="WIX Filter",
            slug="wix-filter",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        self.supplier = Supplier.objects.create(name="GPL", code="gpl")
        self.offer = SupplierOffer.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_sku="WA6342",
            purchase_price="100.00",
            stock_qty=4,
            is_available=True,
        )
        self.job = AutoDbMatchJob.objects.create(
            product=self.product,
            supplier_offer=self.offer,
            supplier_code="gpl",
            raw_brand="WIX",
            normalized_brand="WIX",
            resolved_supplier_id=10,
            article_source_type="payload_manufacturer_article",
            article_value="WA6342",
            canonical_article="WA6342",
            status=AutoDbMatchJob.STATUS_NEW,
        )
        self._seed_local_clone()

    def _auth(self, token: Token) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    def _seed_local_clone(self):
        with connections["auto_db_pro"].cursor() as cursor:
            cursor.execute('CREATE TABLE IF NOT EXISTS article_numbers ("supplierId" INTEGER, "DataSupplierArticleNumber" TEXT)')
            cursor.execute('CREATE TABLE IF NOT EXISTS article_prd ("supplierId" INTEGER, "DataSupplierArticleNumber" TEXT, "productId" INTEGER)')
            cursor.execute('CREATE TABLE IF NOT EXISTS article_links ("supplierId" INTEGER, "DataSupplierArticleNumber" TEXT, "productId" INTEGER)')
            cursor.execute('CREATE TABLE IF NOT EXISTS prd ("id" INTEGER PRIMARY KEY)')
            cursor.execute("TRUNCATE TABLE article_numbers")
            cursor.execute("TRUNCATE TABLE article_prd")
            cursor.execute("TRUNCATE TABLE article_links")
            cursor.execute("TRUNCATE TABLE prd")
            cursor.execute('INSERT INTO article_numbers ("supplierId", "DataSupplierArticleNumber") VALUES (%s, %s)', [10, "WA 6342"])
            cursor.execute('INSERT INTO article_prd ("supplierId", "DataSupplierArticleNumber", "productId") VALUES (%s, %s, %s)', [10, "WA 6342", 99])
            cursor.execute('INSERT INTO prd ("id") VALUES (%s)', [99])

    def test_dashboard_and_jobs_require_staff(self):
        dashboard = reverse("backoffice_api:autodb-matching-dashboard")
        jobs = reverse("backoffice_api:autodb-matching-jobs")

        self.assertEqual(self.client.get(dashboard, **self._auth(self.staff_token)).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(jobs, **self._auth(self.staff_token)).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(dashboard, **self._auth(self.regular_token)).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(jobs, **self._auth(self.regular_token)).status_code, status.HTTP_403_FORBIDDEN)

    def test_manual_local_search_uses_deterministic_variants(self):
        response = self.client.post(
            reverse("backoffice_api:autodb-matching-manual-local"),
            {"supplier_id": 10, "supplier_name": "WIX", "article": "WA6342"},
            format="json",
            **self._auth(self.staff_token),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data["results"][0]
        self.assertEqual(result["status"], "exact_local_found")
        self.assertEqual(result["matched_stored_article"], "WA 6342")
        self.assertIn("WA 6342", result["variants"])
        self.assertIn("fuzzy/OE/cross/name disabled", result["reason"])

    def test_quota_endpoint_returns_recent_points_and_no_secrets(self):
        quota = AutoDbRemoteQuotaState.objects.create(remote_key=REMOTE_QUOTA_KEY)
        AutoDbRemoteQuotaTracker().record_quota_error(
            quota,
            error="ERROR 1226 max_questions for https://user:password@example.test",
            cooldown_minutes=60,
            run_id="run-1",
        )

        response = self.client.get(reverse("backoffice_api:autodb-matching-remote-quota"), **self._auth(self.staff_token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["recent_points"])
        payload_text = str(response.data)
        self.assertNotIn("password@", payload_text)
        self.assertNotIn("user:password", payload_text)

    def test_query_counters_aggregate_by_time_bucket(self):
        quota = AutoDbRemoteQuotaState.objects.create(remote_key=REMOTE_QUOTA_KEY)
        fixed = timezone.now().replace(second=10, microsecond=0)
        tracker = AutoDbRemoteQuotaTracker()

        with patch("apps.autodb.services.matching.quota_tracker.timezone.now", return_value=fixed):
            tracker.record_success(quota, query_count=3, run_id="run-1")
            tracker.record_success(quota, query_count=5, run_id="run-1")

        quota.refresh_from_db()
        self.assertEqual(quota.estimated_queries_used, 8)
        self.assertEqual(len(quota.recent_points_json), 1)
        self.assertEqual(quota.recent_points_json[0]["query_count"], 8)

    def test_remote_quota_error_records_quota_paused_point(self):
        remote_client = Mock()
        remote_client.check_connection.side_effect = AutoDbProRemoteClientError("ERROR 1226 max_questions exceeded")
        lookup_service = SimpleNamespace(storage=SimpleNamespace(remote_client=remote_client), lookup=Mock())

        from apps.autodb.services.matching import AutoDbRemoteLookupService

        result = AutoDbRemoteLookupService(lookup_service=lookup_service).lookup_job(self.job)
        quota = AutoDbRemoteQuotaState.objects.get(remote_key=REMOTE_QUOTA_KEY)

        self.assertEqual(result.status, AutoDbMatchJob.STATUS_QUOTA_PAUSED)
        self.assertEqual(quota.recent_points_json[-1]["status"], "quota_paused")

    @patch("apps.backoffice.api.views.autodb_matching.actions.AutoDbLookupV3ReadOnlyService")
    def test_manual_remote_search_no_upsert_and_no_product_writes(self, lookup_cls):
        before = self._write_counts()
        lookup = lookup_cls.return_value
        lookup.lookup.return_value = SimpleNamespace(
            found=True,
            supplier_id=10,
            supplier_name="WIX",
            canonical_article="WA6342",
            remote_stored_article="WA 6342",
            matched_table="article_numbers",
            matched_source="remote",
            local_hits=0,
            remote_hits=1,
            article_prd_rows=1,
            article_links_rows=0,
            prd_rows=1,
            linkage_present=True,
            remote_queries=2,
            path="lookup_v3_readonly",
            endpoint="mysql://host:3306/db",
        )

        response = self.client.post(
            reverse("backoffice_api:autodb-matching-manual-remote"),
            {"supplier_id": 10, "supplier_name": "WIX", "article": "WA6342"},
            format="json",
            **self._auth(self.staff_token),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["status"], "exact_remote_found")
        self.assertEqual(self._write_counts(), before)
        quota = AutoDbRemoteQuotaState.objects.get(remote_key=REMOTE_QUOTA_KEY)
        self.assertEqual(quota.recent_points_json[-1]["run_id"], "manual-search")
        self.assertGreaterEqual(quota.recent_points_json[-1]["query_count"], 1)
        storage = getattr(lookup, "storage", None)
        self.assertFalse(getattr(getattr(storage, "upsert_rows", None), "called", False))

    def test_manual_remote_search_quota_paused_does_not_write_products(self):
        quota = AutoDbRemoteQuotaState.objects.create(remote_key=REMOTE_QUOTA_KEY)
        AutoDbRemoteQuotaTracker().record_quota_error(quota, error="ERROR 1226 max_questions exceeded", cooldown_minutes=60)
        before = self._write_counts()

        response = self.client.post(
            reverse("backoffice_api:autodb-matching-manual-remote"),
            {"supplier_id": 10, "supplier_name": "WIX", "article": "WA6342"},
            format="json",
            **self._auth(self.staff_token),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["status"], "quota_paused")
        self.assertEqual(self._write_counts(), before)

    def _write_counts(self) -> tuple[int, int, int, int]:
        return (
            Product.objects.count(),
            SupplierOffer.objects.count(),
            ProductPrice.objects.count(),
            ProductImage.objects.count(),
        )
