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

    def test_jobs_endpoint_classifies_remote_found_lookup_mode(self):
        self.job.status = AutoDbMatchJob.STATUS_REMOTE_FOUND
        self.job.save(update_fields=["status", "updated_at"])
        self.job.evidence.create(
            stage="remote_lookup",
            source="lookup_v3_readonly",
            result="exact_remote_found",
            payload_json={"matched_source": "B_norm_article_only:local:article_numbers.DataSupplierArticleNumber"},
        )
        response = self.client.get(reverse("backoffice_api:autodb-matching-jobs"), **self._auth(self.staff_token))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data["results"][0]
        self.assertEqual(row["matching_status"], AutoDbMatchJob.STATUS_REMOTE_FOUND)
        self.assertEqual(row["matching_status_view"], "remote_found_local_clone")
        self.assertEqual(row["lookup_origin"], "local")
        self.assertEqual(row["lookup_method"], "b_norm_article_only")
        self.assertEqual(row["lookup_bucket"], "local_clone_hit")
        self.assertFalse(row["manual_remote_equivalent"])

    def test_dashboard_linked_products_counts_only_full_links(self):
        self.product.autodb_supplier_id = 10
        self.product.autodb_article_number = "WA 6342"
        self.product.autodb_article_key = "10:WA6342"
        self.product.save(update_fields=["autodb_supplier_id", "autodb_article_number", "autodb_article_key", "updated_at"])

        Product.objects.create(
            sku="WIX-002",
            article="WA9999",
            name="WIX Filter 2",
            slug="wix-filter-2",
            brand=self.brand,
            category=self.category,
            is_active=True,
            autodb_supplier_id=10,
            autodb_article_number="",
            autodb_article_key="",
        )

        response = self.client.get(reverse("backoffice_api:autodb-matching-dashboard"), **self._auth(self.staff_token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cards"]["linked_products"], 1)

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

    def test_manual_local_search_resolves_commercial_vehicle_labels_in_compatibility_preview(self):
        with connections["auto_db_pro"].cursor() as cursor:
            cursor.execute(
                'CREATE TABLE IF NOT EXISTS article_li ("supplierId" INTEGER, "DataSupplierArticleNumber" TEXT, "linkageId" INTEGER, "linkageTypeId" TEXT)'
            )
            cursor.execute(
                'CREATE TABLE IF NOT EXISTS commercial_vehicles ("id" INTEGER, "modelid" INTEGER, "description" TEXT, "fulldescription" TEXT, "constructioninterval" TEXT)'
            )
            cursor.execute('CREATE TABLE IF NOT EXISTS models ("id" INTEGER, "description" TEXT, "fulldescription" TEXT)')
            cursor.execute("TRUNCATE TABLE article_li")
            cursor.execute("TRUNCATE TABLE commercial_vehicles")
            cursor.execute("TRUNCATE TABLE models")
            cursor.execute(
                'INSERT INTO article_li ("supplierId", "DataSupplierArticleNumber", "linkageId", "linkageTypeId") VALUES (%s, %s, %s, %s)',
                [10, "WA 6342", 4401, "CommercialVehicle"],
            )
            cursor.execute(
                'INSERT INTO models ("id", "description", "fulldescription") VALUES (%s, %s, %s)',
                [901, "SPRINTER", "MERCEDES-BENZ SPRINTER"],
            )
            cursor.execute(
                'INSERT INTO commercial_vehicles ("id", "modelid", "description", "fulldescription", "constructioninterval") VALUES (%s, %s, %s, %s, %s)',
                [4401, 901, "316 CDI", "MERCEDES-BENZ SPRINTER 316 CDI", "2018-"],
            )

        response = self.client.post(
            reverse("backoffice_api:autodb-matching-manual-local"),
            {"supplier_id": 10, "supplier_name": "WIX", "article": "WA6342"},
            format="json",
            **self._auth(self.staff_token),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data["results"][0]
        preview = result["details"]["compatibility_preview"]
        self.assertTrue(preview)
        first = preview[0]
        self.assertEqual(first["linkage_type"], "CommercialVehicle")
        self.assertEqual(first["label"], "MERCEDES-BENZ SPRINTER 316 CDI")
        self.assertEqual(first["make"], "MERCEDES-BENZ")
        self.assertEqual(first["model"], "SPRINTER")
        self.assertNotEqual(first["label"], "CommercialVehicle #4401")

    def test_quota_endpoint_returns_recent_points_and_no_secrets(self):
        quota = AutoDbRemoteQuotaState.objects.create(remote_key=REMOTE_QUOTA_KEY)
        AutoDbRemoteQuotaTracker().record_quota_error(
            quota,
            error="ERROR 1226 max_questions for https://user:password@example.test User 'user_059a3da6c1' exceeded",
            cooldown_minutes=60,
            run_id="run-1",
        )

        response = self.client.get(reverse("backoffice_api:autodb-matching-remote-quota"), **self._auth(self.staff_token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["recent_points"])
        payload_text = str(response.data)
        self.assertNotIn("password@", payload_text)
        self.assertNotIn("user:password", payload_text)
        self.assertNotIn("user_059a3da6c1", payload_text)

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

    @patch("apps.backoffice.api.views.autodb_matching.actions.manual_bind_product_to_autodb_task")
    def test_manual_create_job_queues_async_bind(self, bind_task):
        bind_task.delay.return_value = SimpleNamespace(id="task-123")
        response = self.client.post(
            reverse("backoffice_api:autodb-matching-manual-create-job"),
            {"product_id": str(self.product.id), "supplier_id": 10, "supplier_name": "WIX", "article": "WA6342", "dispatch_async": True},
            format="json",
            **self._auth(self.staff_token),
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["status"], "queued")
        self.assertEqual(response.data["mode"], "async")
        self.assertTrue(response.data["created"])
        self.assertEqual(response.data["task_id"], "task-123")
        bind_task.delay.assert_called_once()
        kwargs = bind_task.delay.call_args.kwargs
        self.assertEqual(kwargs["product_id"], str(self.product.id))
        self.assertEqual(kwargs["supplier_id"], 10)
        self.assertEqual(kwargs["article_number"], "WA6342")
        self.assertEqual(kwargs["supplier_name"], "WIX")

    @patch("apps.backoffice.api.views.autodb_matching.actions.manual_bind_product_to_autodb_task")
    def test_manual_create_job_can_run_sync(self, bind_task):
        bind_task.return_value = {"status": "bound", "autodb_article_key": "10:WA6342"}
        response = self.client.post(
            reverse("backoffice_api:autodb-matching-manual-create-job"),
            {"product_id": str(self.product.id), "supplier_id": 10, "supplier_name": "WIX", "article": "WA6342", "dispatch_async": False},
            format="json",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "bound")
        self.assertEqual(response.data["mode"], "sync")
        self.assertTrue(response.data["created"])
        bind_task.assert_called_once()

    def _write_counts(self) -> tuple[int, int, int, int]:
        return (
            Product.objects.count(),
            SupplierOffer.objects.count(),
            ProductPrice.objects.count(),
            ProductImage.objects.count(),
        )
