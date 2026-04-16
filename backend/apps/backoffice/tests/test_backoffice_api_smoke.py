from __future__ import annotations

import tempfile
from pathlib import Path

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRowError, ImportRun, ImportSource, SupplierRawOffer
from apps.users.models import User


class BackofficeAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="ops@test.local",
            username="ops",
            password="demo12345",
            is_staff=True,
            is_superuser=False,
        )
        self.regular_user = User.objects.create_user(
            email="customer@test.local",
            username="customer",
            password="demo12345",
            is_staff=False,
            is_superuser=False,
        )

        self.staff_token = Token.objects.create(user=self.staff_user)
        self.regular_token = Token.objects.create(user=self.regular_user)

        self.brand = Brand.objects.create(name="ARAL", slug="aral", is_active=True)
        self.category = Category.objects.create(name="Oils", slug="oils", is_active=True)
        self.product = Product.objects.create(
            sku="AR-20488",
            article="AR-20488",
            name="Aral BlueTronic 10W-40 1Lx12",
            slug="aral-bluetronic-10w40-1l",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.import_source = ImportSource.objects.create(
            code="gpl",
            name="GPL Test",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )
        self.import_run = ImportRun.objects.create(
            source=self.import_source,
            status=ImportRun.STATUS_SUCCESS,
            trigger="test",
            dry_run=False,
            processed_rows=10,
            parsed_rows=8,
            offers_created=3,
            offers_updated=2,
            offers_skipped=3,
            errors_count=2,
            repriced_products=1,
            reindexed_products=0,
        )
        ImportRowError.objects.create(
            run=self.import_run,
            source=self.import_source,
            row_number=1,
            external_sku="bad-sku",
            error_code="missing_price",
            message="missing price",
        )
        SupplierRawOffer.objects.create(
            run=self.import_run,
            source=self.import_source,
            supplier=self.supplier,
            row_number=1,
            external_sku="0001",
            article="AR-20488",
            normalized_article="AR20488",
            brand_name="ARAL",
            normalized_brand="ARAL",
            product_name="Aral BlueTronic 10W-40 1Lx12",
            price="100.00",
            stock_qty=12,
            lead_time_days=0,
            matched_product=self.product,
            is_valid=True,
        )
        SupplierOffer.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_sku="0001",
            purchase_price="100.00",
            stock_qty=12,
            is_available=True,
        )
        ProductPrice.objects.create(
            product=self.product,
            purchase_price="100.00",
            landed_cost="100.00",
            raw_sale_price="120.00",
            final_price="120.00",
        )

    def _auth(self, token: str) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_summary_and_lists_are_available_for_staff(self):
        summary = self.client.get(reverse("backoffice_api:summary"), **self._auth(self.staff_token.key))
        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertIn("totals", summary.data)

        import_sources = self.client.get(reverse("backoffice_api:import-source-list"), **self._auth(self.staff_token.key))
        self.assertEqual(import_sources.status_code, status.HTTP_200_OK)

        import_runs = self.client.get(reverse("backoffice_api:import-run-list"), **self._auth(self.staff_token.key))
        self.assertEqual(import_runs.status_code, status.HTTP_200_OK)

        import_errors = self.client.get(reverse("backoffice_api:import-error-list"), **self._auth(self.staff_token.key))
        self.assertEqual(import_errors.status_code, status.HTTP_200_OK)

        raw_offers = self.client.get(reverse("backoffice_api:raw-offer-list"), **self._auth(self.staff_token.key))
        self.assertEqual(raw_offers.status_code, status.HTTP_200_OK)

        supplier_offers = self.client.get(reverse("backoffice_api:supplier-offer-list"), **self._auth(self.staff_token.key))
        self.assertEqual(supplier_offers.status_code, status.HTTP_200_OK)

        product_prices = self.client.get(reverse("backoffice_api:product-price-list"), **self._auth(self.staff_token.key))
        self.assertEqual(product_prices.status_code, status.HTTP_200_OK)

        autocatalog = self.client.get(reverse("backoffice_api:autocatalog-list"), **self._auth(self.staff_token.key))
        self.assertEqual(autocatalog.status_code, status.HTTP_200_OK)

    def test_non_staff_user_is_forbidden(self):
        response = self.client.get(reverse("backoffice_api:summary"), **self._auth(self.regular_token.key))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_run_source_action_sync_creates_import_run(self):
        payload = """Код;Категорія;Артикул;Найменування;Група ТД;РРЦ грн.;Склад ПЛТВ\n0001;ARAL;AR-20488;Aral BlueTronic 10W-40 1Lx12;ARAL;140.24;15\n"""

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl.csv"
            file_path.write_text(payload, encoding="utf-8")
            self.import_source.input_path = str(file_path)
            self.import_source.save(update_fields=("input_path", "updated_at"))

            response = self.client.post(
                reverse("backoffice_api:action-run-source"),
                {
                    "source_code": self.import_source.code,
                    "dry_run": True,
                    "dispatch_async": False,
                },
                format="json",
                **self._auth(self.staff_token.key),
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["mode"], "sync")
        self.assertIn("run_id", response.data)
        self.assertTrue(ImportRun.objects.filter(id=response.data["run_id"]).exists())
