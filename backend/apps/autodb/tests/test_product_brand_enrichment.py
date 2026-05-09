from __future__ import annotations

from unittest.mock import Mock

from django.test import TestCase

from apps.autodb.services.product_brand_enrichment import AutoDbProductBrandEnrichmentService
from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class ProductBrandEnrichmentServiceTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="LEGACY", slug="legacy", is_active=True)
        self.category = Category.objects.create(name="Filters", slug="filters", is_active=True)
        supplier = Supplier.objects.create(name="GPL Supplier", code="gpl")
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )
        self.run = ImportRun.objects.create(source=self.source, status=ImportRun.STATUS_SUCCESS, trigger="test", dry_run=False)
        self.supplier = supplier

    def _create_raw_offer(self, product: Product, *, brand_name: str) -> None:
        SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            row_number=1,
            external_sku=f"{product.sku}-EXT",
            article=product.article,
            normalized_article=product.article,
            brand_name=brand_name,
            normalized_brand=brand_name,
            product_name=product.name,
            price="1.00",
            stock_qty=1,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
            raw_payload={},
        )

    def test_linked_product_uses_autodb_supplier_over_raw_brand(self):
        product = Product.objects.create(
            sku="WIX-001",
            article="WIX-001",
            name="Filter",
            slug="filter-wix-001",
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=324,
            autodb_article_key="324:WIX-001",
            is_active=True,
        )
        self._create_raw_offer(product, brand_name="RAW WIX")
        service = AutoDbProductBrandEnrichmentService(storage=Mock())
        service._supplier_name_cache[324] = "WIX FILTERS"

        result = service.enrich_product(product=product, dry_run=True)
        self.assertEqual(result.new_brand_name, "WIX FILTERS")
        self.assertEqual(result.brand_source, Product.BRAND_SOURCE_AUTODB_PRO)

    def test_unlinked_product_uses_raw_brand_fallback(self):
        product = Product.objects.create(
            sku="NGK-001",
            article="NGK-001",
            name="Spark Plug",
            slug="spark-ngk-001",
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=None,
            is_active=True,
        )
        self._create_raw_offer(product, brand_name="NGK")
        service = AutoDbProductBrandEnrichmentService(storage=Mock())

        diagnostics = service.diagnose_product(product=product)
        self.assertEqual(diagnostics.proposed_brand_name, "NGK")
        self.assertEqual(diagnostics.proposed_brand_source, Product.BRAND_SOURCE_SUPPLIER_FALLBACK)
