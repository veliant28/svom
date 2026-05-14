from __future__ import annotations

from django.test import TestCase

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services.matching.remaining_alias_binding import AutoDbRemainingAliasBindingService
from apps.catalog.models import Brand, Category, Product


class RemainingAliasBindingServiceTests(TestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        self.service = AutoDbRemainingAliasBindingService()
        self.brand = Brand.objects.create(name='TESTBRAND', slug='testbrand', is_active=True)
        self.category = Category.objects.create(name='Cat', slug='cat', is_active=True)

    def _product(self, *, sku: str, supplier_id: int | None = None, locked: bool = False):
        return Product.objects.create(
            sku=sku,
            article='A1',
            name=f'Name {sku}',
            slug=f'slug-{sku.lower()}',
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=supplier_id,
            brand_manually_locked=locked,
        )

    def test_build_needs_alias_candidates_marks_clean_candidate(self):
        self._product(sku='SKU-1', supplier_id=None)
        coverage = [
            {
                'supplier_code': 'gpl',
                'raw_brand': 'TESTBRAND',
                'normalized_raw_brand': 'TESTBRAND',
                'decision': 'needs_alias',
                'product_count': 1,
                'stock_gt_0_count': 1,
                'product_price_count': 1,
            }
        ]
        suppliers = {100: {'supplier_id': 100, 'description': 'TEST BRAND', 'matchcode': 'TESTBRAND', 'nbrofarticles': 100}}
        by_variant = {'TESTBRAND': {100}}

        rows = self.service._build_needs_alias_candidates(coverage, suppliers, by_variant)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['decision'], 'clean_needs_alias_candidate')
        self.assertEqual(rows[0]['autodb_supplier_id'], 100)

    def test_build_needs_alias_candidates_blocks_existing_different_supplier(self):
        self._product(sku='SKU-1', supplier_id=999)
        coverage = [
            {
                'supplier_code': 'gpl',
                'raw_brand': 'TESTBRAND',
                'normalized_raw_brand': 'TESTBRAND',
                'decision': 'needs_alias',
                'product_count': 1,
                'stock_gt_0_count': 1,
                'product_price_count': 1,
            }
        ]
        suppliers = {100: {'supplier_id': 100, 'description': 'TEST BRAND', 'matchcode': 'TESTBRAND', 'nbrofarticles': 100}}
        by_variant = {'TESTBRAND': {100}}

        rows = self.service._build_needs_alias_candidates(coverage, suppliers, by_variant)

        self.assertEqual(rows[0]['decision'], 'blocked')
        self.assertGreater(rows[0]['products_existing_different_supplier'], 0)

    def test_build_dry_run_blocks_alias_conflict(self):
        self._product(sku='SKU-1', supplier_id=None)
        AutoDbSupplierBrandAlias.objects.create(
            raw_brand='TESTBRAND',
            autodb_supplier_id=200,
            autodb_supplier_name='OTHER',
            source=AutoDbSupplierBrandAlias.SOURCE_MANUAL,
            confidence='100.00',
            manual_confirmed=True,
            is_active=True,
        )

        candidates = [
            {
                'supplier_code': 'gpl',
                'raw_brand': 'TESTBRAND',
                'normalized_raw_brand': 'TESTBRAND',
                'autodb_supplier_id': 100,
                'autodb_supplier_name': 'TEST BRAND',
                'decision': 'clean_needs_alias_candidate',
                'candidate_status': 'single_candidate',
                'products_existing_different_supplier': 0,
            }
        ]

        rows, summary, clean_rows = self.service._build_dry_run(candidates)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['alias_action'], 'blocked_conflict')
        self.assertEqual(summary['aliases_blocked_conflict'], 1)
        self.assertEqual(len(clean_rows), 0)
