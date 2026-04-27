from __future__ import annotations

from types import SimpleNamespace

from django.test import TestCase
from django.utils import timezone

from apps.backoffice.api.serializers import BackofficeCatalogProductSerializer
from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.users.models import User


class CatalogProductSerializerCategorySyncTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            email="serializer-sync@test.local",
            first_name="serializer-sync",
            password="demo12345",
            is_staff=True,
        )
        self.brand = Brand.objects.create(name="BOSCH", slug="bosch-sync", is_active=True)
        self.category_old = Category.objects.create(name="Filters Sync", slug="filters-sync", is_active=True)
        self.category_new = Category.objects.create(name="Brakes Sync", slug="brakes-sync", is_active=True)
        self.product = Product.objects.create(
            sku="SYNC-001",
            article="SYNC-001",
            name="Sync Product",
            slug="sync-product",
            brand=self.brand,
            category=self.category_old,
            is_active=True,
        )
        self.supplier = Supplier.objects.create(name="Sync Supplier", code="sync-supplier")
        self.source = ImportSource.objects.create(
            code="sync-source",
            name="Sync Source",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_UTR,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )
        self.run = ImportRun.objects.create(
            source=self.source,
            status=ImportRun.STATUS_SUCCESS,
            trigger="test",
            dry_run=False,
            processed_rows=1,
            parsed_rows=1,
            offers_created=1,
            offers_updated=0,
            offers_skipped=0,
            errors_count=0,
            repriced_products=0,
            reindexed_products=0,
        )
        self.raw_offer = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            row_number=1,
            external_sku="SYNC-001",
            article="SYNC-001",
            normalized_article="SYNC001",
            brand_name="BOSCH",
            normalized_brand="BOSCH",
            product_name="Sync Product",
            price="100.00",
            stock_qty=2,
            lead_time_days=0,
            matched_product=self.product,
            is_valid=True,
            raw_payload={},
        )
        self.offer_seen_at = timezone.now()
        self.supplier_offer = SupplierOffer.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_sku="SYNC-001",
            purchase_price="100.00",
            stock_qty=2,
            is_available=True,
            last_seen_at=self.offer_seen_at,
        )

    def test_category_change_syncs_raw_offer_manual_mapping(self):
        serializer = BackofficeCatalogProductSerializer(
            self.product,
            data={"category": str(self.category_new.id)},
            partial=True,
            context={"request": SimpleNamespace(user=self.actor)},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.product.refresh_from_db()
        self.assertEqual(self.product.category_id, self.category_new.id)

        self.raw_offer.refresh_from_db()
        self.assertEqual(self.raw_offer.mapped_category_id, self.category_new.id)
        self.assertEqual(
            self.raw_offer.category_mapping_status,
            SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
        )
        self.assertEqual(
            self.raw_offer.category_mapping_reason,
            SupplierRawOffer.CATEGORY_MAPPING_REASON_MANUAL,
        )
        self.assertEqual(self.raw_offer.category_mapped_by_id, self.actor.id)

    def test_serializer_exposes_supplier_offer_seen_at(self):
        serializer = BackofficeCatalogProductSerializer(self.product)

        self.assertEqual(serializer.data["supplier_offer_seen_at"], self.offer_seen_at)
