from __future__ import annotations

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Brand, Product
from apps.catalog.services.svom_sku import (
    build_deterministic_svom_sku,
    ensure_product_svom_sku,
    is_valid_svom_sku,
)
from apps.pricing.models import Supplier, SupplierOffer


class SkuGenerationTests(TestCase):
    def setUp(self) -> None:
        self.brand = Brand.objects.create(name="Brand", slug="brand", is_active=True)

    def _make_product(self, suffix: str) -> Product:
        return Product.objects.create(
            sku=f"SKU-{suffix}",
            article=f"ART-{suffix}",
            name=f"Product {suffix}",
            slug=f"product-{suffix}",
            brand=self.brand,
            is_active=True,
        )

    def test_format_is_valid_and_contains_letters_in_order(self):
        product = self._make_product("A")
        value = build_deterministic_svom_sku(product_id=product.id, counter=0)
        self.assertTrue(is_valid_svom_sku(value))
        self.assertRegex(value, r"^\dS\dV\dO\dM\d{4}$")

    def test_generator_is_stable_for_same_product_id(self):
        product = self._make_product("B")
        first = build_deterministic_svom_sku(product_id=product.id, counter=0)
        second = build_deterministic_svom_sku(product_id=product.id, counter=0)
        self.assertEqual(first, second)

    def test_collision_retry_generates_unique_value(self):
        product_one = self._make_product("C1")
        product_two = self._make_product("C2")

        first_candidate_for_second = build_deterministic_svom_sku(product_id=product_two.id, counter=0)
        product_one.svom_sku = first_candidate_for_second
        product_one.save(update_fields=["svom_sku", "updated_at"])

        generated, counter, created = ensure_product_svom_sku(product_two, save=True)
        self.assertTrue(created)
        self.assertGreater(counter, 0)
        self.assertNotEqual(generated, first_candidate_for_second)
        self.assertTrue(is_valid_svom_sku(generated))

    def test_does_not_overwrite_existing_svom_sku(self):
        product = self._make_product("D")
        product.svom_sku = "1S5V0O4M9273"
        product.save(update_fields=["svom_sku", "updated_at"])

        generated, counter, created = ensure_product_svom_sku(product, save=True)
        self.assertEqual(generated, "1S5V0O4M9273")
        self.assertEqual(counter, 0)
        self.assertFalse(created)


class SkuBackfillCommandTests(TestCase):
    def setUp(self) -> None:
        self.brand = Brand.objects.create(name="Brand", slug="brand", is_active=True)
        self.gpl = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.utr = Supplier.objects.create(name="UTR", code="utr", is_active=True)

    def _product(self, suffix: str, *, svom_sku: str | None = None) -> Product:
        return Product.objects.create(
            sku=f"SKU-{suffix}",
            article=f"ART-{suffix}",
            name=f"Product {suffix}",
            slug=f"product-{suffix}",
            brand=self.brand,
            svom_sku=svom_sku,
            is_active=True,
        )

    def test_scope_all_dry_run_does_not_write(self):
        product = self._product("DRY")
        SupplierOffer.objects.create(
            supplier=self.utr,
            product=product,
            supplier_sku="UTR-DRY",
            purchase_price="10.00",
            stock_qty=1,
            is_available=True,
        )

        call_command(
            "backfill_svom_sku_multi_offer",
            scope="all",
            export_csv="/tmp/test_svom_sku_scope_all_dry.csv",
            export_md="/tmp/test_svom_sku_scope_all_dry.md",
        )

        product.refresh_from_db()
        self.assertEqual(product.svom_sku, None)

    def test_scope_all_apply_sets_only_missing_and_preserves_existing_keys(self):
        existing = self._product("EX", svom_sku="1S5V0O4M9273")
        gpl_only = self._product("GPL")
        utr_only = self._product("UTR")
        multi = self._product("MULTI")

        gpl_offer = SupplierOffer.objects.create(
            supplier=self.gpl,
            product=gpl_only,
            supplier_sku="GPL-SUP-1",
            purchase_price="10.00",
            stock_qty=1,
            is_available=True,
        )
        utr_offer = SupplierOffer.objects.create(
            supplier=self.utr,
            product=utr_only,
            supplier_sku="UTR-SUP-1",
            purchase_price="10.00",
            stock_qty=1,
            is_available=True,
        )
        SupplierOffer.objects.create(
            supplier=self.gpl,
            product=multi,
            supplier_sku="GPL-SUP-2",
            purchase_price="10.00",
            stock_qty=1,
            is_available=True,
        )
        multi_offer_utr = SupplierOffer.objects.create(
            supplier=self.utr,
            product=multi,
            supplier_sku="UTR-SUP-2",
            purchase_price="20.00",
            stock_qty=1,
            is_available=True,
        )

        before = {
            "existing_sku": existing.sku,
            "gpl_sku": gpl_only.sku,
            "utr_sku": utr_only.sku,
            "multi_sku": multi.sku,
            "gpl_supplier_sku": gpl_offer.supplier_sku,
            "utr_supplier_sku": utr_offer.supplier_sku,
            "multi_utr_supplier_sku": multi_offer_utr.supplier_sku,
        }

        call_command(
            "backfill_svom_sku_multi_offer",
            scope="all",
            apply=True,
            export_csv="/tmp/test_svom_sku_scope_all_apply.csv",
            export_md="/tmp/test_svom_sku_scope_all_apply.md",
        )

        existing.refresh_from_db()
        gpl_only.refresh_from_db()
        utr_only.refresh_from_db()
        multi.refresh_from_db()
        gpl_offer.refresh_from_db()
        utr_offer.refresh_from_db()
        multi_offer_utr.refresh_from_db()

        self.assertEqual(existing.svom_sku, "1S5V0O4M9273")
        self.assertTrue(is_valid_svom_sku(gpl_only.svom_sku))
        self.assertTrue(is_valid_svom_sku(utr_only.svom_sku))
        self.assertTrue(is_valid_svom_sku(multi.svom_sku))
        self.assertEqual(len({gpl_only.svom_sku, utr_only.svom_sku, multi.svom_sku}), 3)

        self.assertEqual(existing.sku, before["existing_sku"])
        self.assertEqual(gpl_only.sku, before["gpl_sku"])
        self.assertEqual(utr_only.sku, before["utr_sku"])
        self.assertEqual(multi.sku, before["multi_sku"])
        self.assertEqual(gpl_offer.supplier_sku, before["gpl_supplier_sku"])
        self.assertEqual(utr_offer.supplier_sku, before["utr_supplier_sku"])
        self.assertEqual(multi_offer_utr.supplier_sku, before["multi_utr_supplier_sku"])
