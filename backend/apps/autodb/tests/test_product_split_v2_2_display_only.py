from __future__ import annotations

from collections import defaultdict

from django.test import TestCase

from apps.autodb.services.matching.product_split_v2_2_display_only import (
    AutoDbProductSplitV22DisplayOnlyPlanner,
    DisplayOnlyCandidate,
)
from apps.catalog.models import Brand, Category, Product
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbProductSplitV22DisplayOnlyPlannerTests(TestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        self.brand_keep = Brand.objects.create(name="POLMO", slug="v22-polmo", is_active=True)
        self.brand_move = Brand.objects.create(name="LOTOS", slug="v22-lotos", is_active=True)
        self.category = Category.objects.create(name="Exhaust", slug="v22-exhaust", is_active=True)

        self.gpl = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.utr = Supplier.objects.create(name="UTR", code="utr", is_active=True)

        self.source_gpl = ImportSource.objects.create(
            code="v22-gpl-source",
            name="V22 GPL source",
            supplier=self.gpl,
            parser_type=ImportSource.PARSER_GPL,
            is_active=True,
        )
        self.source_utr = ImportSource.objects.create(
            code="v22-utr-source",
            name="V22 UTR source",
            supplier=self.utr,
            parser_type=ImportSource.PARSER_UTR,
            is_active=True,
        )
        self.run_gpl = ImportRun.objects.create(source=self.source_gpl, status=ImportRun.STATUS_SUCCESS, trigger="test")
        self.run_utr = ImportRun.objects.create(source=self.source_utr, status=ImportRun.STATUS_SUCCESS, trigger="test")

    def _build_base_case(self, *, with_trusted_key: bool = False, extra_keep_offer: bool = False):
        product = Product.objects.create(
            sku="SKU-V22-BASE",
            svom_sku="SVOM-V22-BASE",
            article="01111",
            name="POLMO exhaust",
            slug="v22-base",
            brand=self.brand_keep,
            category=self.category,
            display_brand_name="POLMO",
            autodb_supplier_id=None,
            autodb_supplier_name="",
            autodb_article_key="KEY-LOCK" if with_trusted_key else "",
            is_active=True,
        )
        keep_offer = SupplierOffer.objects.create(
            supplier=self.gpl,
            product=product,
            supplier_sku="01111",
            currency="UAH",
            purchase_price="500.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=2,
            lead_time_days=0,
            is_available=True,
        )
        move_offer = SupplierOffer.objects.create(
            supplier=self.utr,
            product=product,
            supplier_sku="LO01111",
            currency="UAH",
            purchase_price="120.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=1,
            lead_time_days=0,
            is_available=True,
        )
        if extra_keep_offer:
            SupplierOffer.objects.create(
                supplier=self.gpl,
                product=product,
                supplier_sku="01111-ALT",
                currency="UAH",
                purchase_price="510.00",
                price_levels=[],
                logistics_cost="0.00",
                extra_cost="0.00",
                stock_qty=1,
                lead_time_days=0,
                is_available=True,
            )

        ProductPrice.objects.create(
            product=product,
            currency="UAH",
            purchase_price="500.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="500.00",
            raw_sale_price="550.00",
            final_price="550.00",
        )

        SupplierRawOffer.objects.create(
            run=self.run_gpl,
            source=self.source_gpl,
            supplier=self.gpl,
            external_sku="01111",
            article="01111",
            normalized_article="01111",
            brand_name="POLMO",
            normalized_brand="POLMO",
            product_name="POLMO exhaust",
            price="500.00",
            stock_qty=2,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        move_raw = SupplierRawOffer.objects.create(
            run=self.run_utr,
            source=self.source_utr,
            supplier=self.utr,
            external_sku="LO01111",
            article="01111",
            normalized_article="01111",
            brand_name="LOTOS",
            normalized_brand="LOTOS",
            product_name="LOTOS exhaust",
            price="120.00",
            stock_qty=1,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )

        candidate = DisplayOnlyCandidate(
            product_id=str(product.id),
            original_sku=str(product.svom_sku),
            keep_group=f"POLMO|01111[1]:{keep_offer.id}",
            move_group=f"LOTOS|01111[1]:{move_offer.id}",
            move_brand="LOTOS",
            move_brand_norm="LOTOS",
            supplier_code="utr",
            moved_offer_ids=(str(move_offer.id),),
        )
        return product, keep_offer, move_offer, move_raw, candidate

    def test_no_supplier_moved_brand_can_be_display_only_clean_if_deterministic(self):
        _product, _keep_offer, _move_offer, _move_raw, candidate = self._build_base_case()
        planner = AutoDbProductSplitV22DisplayOnlyPlanner()
        planner._supplier_exact_index = defaultdict(set)  # force no-supplier classification
        planner._supplier_variant_index = defaultdict(set)

        plan = planner.plan(candidate)
        self.assertTrue(plan.clean_display_only)
        self.assertEqual(plan.supplier_candidate_classification, "no_supplier_candidate")

    def test_display_only_sets_new_autodb_supplier_null(self):
        _product, _keep_offer, _move_offer, _move_raw, candidate = self._build_base_case()
        planner = AutoDbProductSplitV22DisplayOnlyPlanner()
        planner._supplier_exact_index = defaultdict(set)
        planner._supplier_variant_index = defaultdict(set)

        plan = planner.plan(candidate)
        self.assertIsNone(plan.proposed_new_autodb_supplier_id)
        self.assertEqual(plan.proposed_new_autodb_supplier_name, "")
        self.assertEqual(plan.proposed_new_brand_source, "split_offer_brand")

    def test_display_only_blocks_empty_or_invalid_brand(self):
        _product, _keep_offer, _move_offer, _move_raw, candidate = self._build_base_case()
        candidate = DisplayOnlyCandidate(
            product_id=candidate.product_id,
            original_sku=candidate.original_sku,
            keep_group=candidate.keep_group,
            move_group=candidate.move_group,
            move_brand="",
            move_brand_norm="",
            supplier_code=candidate.supplier_code,
            moved_offer_ids=candidate.moved_offer_ids,
        )
        planner = AutoDbProductSplitV22DisplayOnlyPlanner()
        plan = planner.plan(candidate)
        self.assertIn("display_only_invalid_move_brand", set(plan.blockers))

    def test_display_only_blocks_ambiguous_productprice_basis(self):
        _product, _keep_offer, _move_offer, _move_raw, candidate = self._build_base_case(extra_keep_offer=True)
        planner = AutoDbProductSplitV22DisplayOnlyPlanner()
        planner._supplier_exact_index = defaultdict(set)
        planner._supplier_variant_index = defaultdict(set)

        plan = planner.plan(candidate)
        self.assertIn("productprice_basis_ambiguous", set(plan.blockers))

    def test_display_only_blocks_trusted_link_conflict(self):
        _product, _keep_offer, _move_offer, _move_raw, candidate = self._build_base_case(with_trusted_key=True)
        planner = AutoDbProductSplitV22DisplayOnlyPlanner()
        planner._supplier_exact_index = defaultdict(set)
        planner._supplier_variant_index = defaultdict(set)

        plan = planner.plan(candidate)
        self.assertIn("trusted_link_conflict", set(plan.blockers))

    def test_display_only_marks_new_product_excluded_from_autodb_matching(self):
        _product, _keep_offer, _move_offer, _move_raw, candidate = self._build_base_case()
        planner = AutoDbProductSplitV22DisplayOnlyPlanner()
        planner._supplier_exact_index = defaultdict(set)
        planner._supplier_variant_index = defaultdict(set)

        plan = planner.plan(candidate)
        self.assertEqual(plan.queue_state_after_split, "new_product_autodb_matching_excluded_unresolved_supplier")

    def test_exact_supplier_case_stays_strict_path_unless_configured(self):
        _product, _keep_offer, _move_offer, _move_raw, candidate = self._build_base_case()
        planner = AutoDbProductSplitV22DisplayOnlyPlanner()
        planner._supplier_exact_index = defaultdict(set)
        planner._supplier_exact_index["LOTOS"] = {123}
        planner._supplier_variant_index = defaultdict(set)

        blocked_plan = planner.plan(candidate, allow_exact_supplier_display_only=False)
        self.assertIn("exact_supplier_requires_strict_binding_path", set(blocked_plan.blockers))

        allowed_plan = planner.plan(candidate, allow_exact_supplier_display_only=True)
        self.assertNotIn("exact_supplier_requires_strict_binding_path", set(allowed_plan.blockers))

    def test_no_writes_in_dry_run(self):
        _product, _keep_offer, _move_offer, _move_raw, candidate = self._build_base_case()
        planner = AutoDbProductSplitV22DisplayOnlyPlanner()
        planner._supplier_exact_index = defaultdict(set)
        planner._supplier_variant_index = defaultdict(set)

        before = {
            "product": Product.objects.count(),
            "offer": SupplierOffer.objects.count(),
            "raw": SupplierRawOffer.objects.count(),
            "price": ProductPrice.objects.count(),
            "fitment": ProductFitment.objects.count(),
        }
        _ = planner.plan(candidate)
        after = {
            "product": Product.objects.count(),
            "offer": SupplierOffer.objects.count(),
            "raw": SupplierRawOffer.objects.count(),
            "price": ProductPrice.objects.count(),
            "fitment": ProductFitment.objects.count(),
        }
        self.assertEqual(before, after)
