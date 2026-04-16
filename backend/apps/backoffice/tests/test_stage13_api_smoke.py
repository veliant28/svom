from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.supplier_imports.services import ImportQualityService
from apps.users.models import User


class Stage13BackofficeAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="stage13@test.local",
            username="stage13",
            password="demo12345",
            is_staff=True,
        )
        self.token = Token.objects.create(user=self.staff)

        brand = Brand.objects.create(name="ARAL", slug="aral", is_active=True)
        category = Category.objects.create(name="Oils", slug="oils", is_active=True)
        self.product = Product.objects.create(
            sku="AR-20488",
            article="AR-20488",
            name="Aral",
            slug="aral-stage13",
            brand=brand,
            category=category,
            is_active=True,
        )

        supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
            is_auto_import_enabled=True,
            schedule_cron="*/30 * * * *",
            schedule_timezone="Europe/Kyiv",
        )
        self.run = ImportRun.objects.create(
            source=self.source,
            status=ImportRun.STATUS_PARTIAL,
            trigger="test",
            processed_rows=5,
            errors_count=1,
        )
        SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=supplier,
            external_sku="0001",
            article="AR-20488",
            normalized_article="AR20488",
            brand_name="ARAL",
            normalized_brand="ARAL",
            product_name="Aral",
            currency="UAH",
            price=Decimal("100.00"),
            stock_qty=1,
            match_status=SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED,
            matched_product=self.product,
            is_valid=True,
        )
        ImportQualityService().refresh_for_run(run=self.run)

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

    def test_schedules_dictionaries_and_quality_endpoints(self):
        schedules = self.client.get(reverse("backoffice_api:import-schedule-list"), **self._auth())
        self.assertEqual(schedules.status_code, status.HTTP_200_OK)

        update = self.client.patch(
            reverse("backoffice_api:import-schedule-update", kwargs={"id": str(self.source.id)}),
            {"is_auto_import_enabled": False},
            format="json",
            **self._auth(),
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)

        alias_create = self.client.post(
            reverse("backoffice_api:brand-alias-list-create"),
            {
                "source": str(self.source.id),
                "supplier": str(self.source.supplier_id),
                "supplier_brand_alias": "MAHLE - KNECHT",
                "canonical_brand_name": "MAHLE",
                "is_active": True,
                "priority": 100,
            },
            format="json",
            **self._auth(),
        )
        self.assertEqual(alias_create.status_code, status.HTTP_201_CREATED)

        rule_create = self.client.post(
            reverse("backoffice_api:article-rule-list-create"),
            {
                "source": str(self.source.id),
                "name": "Strip OEM prefix",
                "rule_type": "strip_prefix",
                "pattern": "OEM-",
                "replacement": "",
                "is_active": True,
                "priority": 100,
            },
            format="json",
            **self._auth(),
        )
        self.assertEqual(rule_create.status_code, status.HTTP_201_CREATED)

        quality_summary = self.client.get(reverse("backoffice_api:import-quality-summary"), **self._auth())
        self.assertEqual(quality_summary.status_code, status.HTTP_200_OK)
        self.assertIn("totals", quality_summary.data)

        quality_list = self.client.get(reverse("backoffice_api:import-quality-list"), **self._auth())
        self.assertEqual(quality_list.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(quality_list.data["count"], 1)

        quality_detail = self.client.get(
            reverse("backoffice_api:import-quality-detail", kwargs={"run_id": str(self.run.id)}),
            **self._auth(),
        )
        self.assertEqual(quality_detail.status_code, status.HTTP_200_OK)

        quality_compare = self.client.get(
            reverse("backoffice_api:import-quality-compare", kwargs={"run_id": str(self.run.id)}),
            **self._auth(),
        )
        self.assertEqual(quality_compare.status_code, status.HTTP_200_OK)
        self.assertIn("delta", quality_compare.data)
