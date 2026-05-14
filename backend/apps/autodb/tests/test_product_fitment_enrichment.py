from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.autodb.services.product_fitment_enrichment import AutoDbProductFitmentEnrichmentService
from apps.catalog.models import Brand, Category, Product
from apps.compatibility.models import ProductFitment


class AutoDbProductFitmentEnrichmentServiceTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Brand", slug="brand", is_active=True)
        self.category = Category.objects.create(name="Category", slug="category", is_active=True)
        self.product = Product.objects.create(
            sku="FIT-1",
            slug="fit-1",
            name="Fitment product",
            article="A-1",
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=324,
            autodb_article_number="92131E",
            autodb_article_key="324:92131E",
            available_stock_qty_cached=5,
            is_active=True,
        )

    def _service(self) -> AutoDbProductFitmentEnrichmentService:
        return AutoDbProductFitmentEnrichmentService()

    def _create_manual_fitment(self) -> ProductFitment:
        return ProductFitment.objects.create(
            product=self.product,
            source=ProductFitment.SOURCE_MANUAL,
            note="Manual fitment",
            is_exact=True,
            autodb_passanger_car_id=501,
            linkage_type="PassengerCar",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            manual_locked=True,
        )

    def test_fitments_created_from_passenger_car_linkage(self):
        service = self._service()
        article_rows = [
            {
                "supplierId": 324,
                "DataSupplierArticleNumber": "92131E",
                "linkageTypeId": "PassengerCar",
                "linkageId": 101,
            }
        ]
        with (
            patch.object(service, "_find_article_li_rows", return_value=article_rows),
            patch.object(service, "_find_existing_passanger_car_ids", return_value={101}),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.assertEqual(result.fitments_created, 1)
        fitment = ProductFitment.objects.get(product=self.product, source=ProductFitment.SOURCE_AUTODB_PRO)
        self.assertEqual(fitment.autodb_passanger_car_id, 101)
        self.assertEqual(fitment.linkage_type, "PassengerCar")

    def test_commercial_vehicle_linkage_is_saved(self):
        service = self._service()
        with patch.object(
            service,
            "_find_article_li_rows",
            return_value=[
                {"supplierId": 324, "DataSupplierArticleNumber": "92131E", "linkageTypeId": "CommercialVehicle", "linkageId": 900}
            ],
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.assertEqual(result.fitments_created, 1)
        fitment = ProductFitment.objects.get(product=self.product, source=ProductFitment.SOURCE_AUTODB_PRO)
        self.assertEqual(fitment.autodb_passanger_car_id, 900)
        self.assertEqual(fitment.linkage_type, "CommercialVehicle")

    def test_missing_passanger_car_skipped(self):
        service = self._service()
        with (
            patch.object(
                service,
                "_find_article_li_rows",
                return_value=[
                    {"supplierId": 324, "DataSupplierArticleNumber": "92131E", "linkageTypeId": "PassengerCar", "linkageId": 777}
                ],
            ),
            patch.object(service, "_find_existing_passanger_car_ids", return_value=set()),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.assertTrue(result.skipped_missing_passanger_car)
        self.assertEqual(ProductFitment.objects.filter(product=self.product, source=ProductFitment.SOURCE_AUTODB_PRO).count(), 0)

    def test_missing_passenger_car_does_not_block_other_linkage_types(self):
        service = self._service()
        with (
            patch.object(
                service,
                "_find_article_li_rows",
                return_value=[
                    {"supplierId": 324, "DataSupplierArticleNumber": "92131E", "linkageTypeId": "PassengerCar", "linkageId": 777},
                    {"supplierId": 324, "DataSupplierArticleNumber": "92131E", "linkageTypeId": "CommercialVehicle", "linkageId": 900},
                ],
            ),
            patch.object(service, "_find_existing_passanger_car_ids", return_value=set()),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.assertEqual(result.fitments_created, 1)
        fitment = ProductFitment.objects.get(product=self.product, source=ProductFitment.SOURCE_AUTODB_PRO)
        self.assertEqual(fitment.autodb_passanger_car_id, 900)
        self.assertEqual(fitment.linkage_type, "CommercialVehicle")

    def test_repeated_run_no_duplicates(self):
        service = self._service()
        rows = [{"supplierId": 324, "DataSupplierArticleNumber": "92131E", "linkageTypeId": "PassengerCar", "linkageId": 101}]
        with (
            patch.object(service, "_find_article_li_rows", return_value=rows),
            patch.object(service, "_find_existing_passanger_car_ids", return_value={101}),
        ):
            first = service.enrich_product(product=self.product, dry_run=False)
            second = service.enrich_product(product=self.product, dry_run=False)

        self.assertEqual(first.fitments_created, 1)
        self.assertEqual(second.fitments_created, 0)
        self.assertEqual(ProductFitment.objects.filter(product=self.product, source=ProductFitment.SOURCE_AUTODB_PRO).count(), 1)

    def test_product_without_link_skipped(self):
        self.product.autodb_supplier_id = None
        self.product.autodb_article_number = ""
        self.product.save(update_fields=("autodb_supplier_id", "autodb_article_number", "updated_at"))
        service = self._service()

        result = service.enrich_product(product=self.product, dry_run=False)

        self.assertTrue(result.skipped_no_autodb_link)

    def test_no_article_li_rows_skipped(self):
        service = self._service()
        with patch.object(service, "_find_article_li_rows", return_value=[]):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.assertTrue(result.skipped_no_article_li)

    def test_manual_fitments_are_not_overwritten_or_deleted(self):
        manual = self._create_manual_fitment()
        service = self._service()
        rows = [{"supplierId": 324, "DataSupplierArticleNumber": "92131E", "linkageTypeId": "PassengerCar", "linkageId": 101}]
        with (
            patch.object(service, "_find_article_li_rows", return_value=rows),
            patch.object(service, "_find_existing_passanger_car_ids", return_value={101}),
        ):
            service.enrich_product(product=self.product, dry_run=False)

        self.assertTrue(ProductFitment.objects.filter(id=manual.id).exists())
        manual.refresh_from_db()
        self.assertEqual(manual.source, ProductFitment.SOURCE_MANUAL)

    def test_stale_marked_non_destructive(self):
        ProductFitment.objects.create(
            product=self.product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=404,
            linkage_type="PassengerCar",
            autodb_article_key="324:92131E",
            supplier_id=324,
            article_number="92131E",
        )
        service = self._service()

        with (
            patch.object(service, "_find_article_li_rows", return_value=[]),
            patch.object(service, "_find_existing_passanger_car_ids", return_value=set()),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.assertGreaterEqual(result.stale_marked, 1)
        fitment = ProductFitment.objects.get(product=self.product, source=ProductFitment.SOURCE_AUTODB_PRO)
        self.assertTrue(fitment.is_stale)
        self.assertEqual(fitment.stale_reason, "missing_from_latest_import")

    def test_manual_locked_autodb_fitment_is_not_overwritten(self):
        ProductFitment.objects.create(
            product=self.product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=101,
            linkage_type="PassengerCar",
            autodb_article_key="old",
            supplier_id=324,
            article_number="OLD",
            manual_locked=True,
        )
        service = self._service()
        rows = [{"supplierId": 324, "DataSupplierArticleNumber": "92131E", "linkageTypeId": "PassengerCar", "linkageId": 101}]
        with (
            patch.object(service, "_find_article_li_rows", return_value=rows),
            patch.object(service, "_find_existing_passanger_car_ids", return_value={101}),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.assertTrue(result.skipped_manual_locked)
        fitment = ProductFitment.objects.get(product=self.product, source=ProductFitment.SOURCE_AUTODB_PRO)
        self.assertEqual(fitment.article_number, "OLD")

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    def test_utr_not_called_and_price_stock_unchanged(self, utr_cls):
        service = self._service()
        before_stock = self.product.available_stock_qty_cached
        rows = [{"supplierId": 324, "DataSupplierArticleNumber": "92131E", "linkageTypeId": "PassengerCar", "linkageId": 101}]
        with (
            patch.object(service, "_find_article_li_rows", return_value=rows),
            patch.object(service, "_find_existing_passanger_car_ids", return_value={101}),
        ):
            service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(self.product.available_stock_qty_cached, before_stock)
        utr_cls.assert_not_called()
