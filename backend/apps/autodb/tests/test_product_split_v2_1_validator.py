from __future__ import annotations

from django.test import TestCase

from apps.autodb.services.matching.product_split_v2_1_validator import (
    AutoDbProductSplitV21Validator,
    SplitV21Candidate,
)
from apps.autodb.services.matching.product_split_v2_planner import AutoDbProductSplitV2Planner
from apps.catalog.models import Brand, Category, Product
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbProductSplitV21ValidatorTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.validator = AutoDbProductSplitV21Validator()
        self.brand_polmo = Brand.objects.create(name="POLMO", slug="v21-polmo", is_active=True)
        self.brand_febi = Brand.objects.create(name="FEBI BILSTEIN", slug="v21-febi", is_active=True)
        self.brand_mann = Brand.objects.create(name="MANN-FILTER", slug="v21-mann", is_active=True)
        self.brand_mahle = Brand.objects.create(name="MAHLE ORIGINAL", slug="v21-mahle", is_active=True)
        self.category = Category.objects.create(name="Exhaust", slug="v21-exhaust", is_active=True)
        self.gpl = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.utr = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.source_gpl = ImportSource.objects.create(
            code="v21-gpl-source",
            name="V21 GPL source",
            supplier=self.gpl,
            parser_type=ImportSource.PARSER_GPL,
            is_active=True,
        )
        self.source_utr = ImportSource.objects.create(
            code="v21-utr-source",
            name="V21 UTR source",
            supplier=self.utr,
            parser_type=ImportSource.PARSER_UTR,
            is_active=True,
        )
        self.run_gpl = ImportRun.objects.create(source=self.source_gpl, status=ImportRun.STATUS_SUCCESS, trigger="test")
        self.run_utr = ImportRun.objects.create(source=self.source_utr, status=ImportRun.STATUS_SUCCESS, trigger="test")

    def test_successful_polmo_febi_case_passes(self):
        product = Product.objects.create(
            sku="SKU-V21-OK",
            svom_sku="SVOM-V21-OK",
            article="01111",
            name="POLMO exhaust",
            slug="v21-polmo-source",
            brand=self.brand_polmo,
            category=self.category,
            display_brand_name="POLMO",
            autodb_supplier_id=101,
            autodb_supplier_name="FEBI BILSTEIN",
            is_active=True,
        )
        keep_offer = SupplierOffer.objects.create(
            supplier=self.gpl,
            product=product,
            supplier_sku="01111",
            currency="UAH",
            purchase_price="2619.00",
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
            supplier_sku="FE01111",
            currency="UAH",
            purchase_price="138.88",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=0,
            lead_time_days=0,
            is_available=False,
        )
        ProductPrice.objects.create(
            product=product,
            currency="UAH",
            purchase_price="2619.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="2619.00",
            raw_sale_price="2619.00",
            final_price="2619.00",
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
            price="2619.00",
            stock_qty=2,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        raw_move = SupplierRawOffer.objects.create(
            run=self.run_utr,
            source=self.source_utr,
            supplier=self.utr,
            external_sku="FE01111",
            article="01111",
            normalized_article="01111",
            brand_name="FEBI BILSTEIN",
            normalized_brand="FEBIBILSTEIN",
            product_name="FEBI part",
            price="138.88",
            stock_qty=0,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        candidate = SplitV21Candidate(
            case_label="ok",
            sku=str(product.svom_sku or ""),
            source_product_id=str(product.id),
            keep_group="POLMO|01111",
            move_group="FEBIBILSTEIN|01111",
            keep_brand_norm="POLMO",
            move_brand_norm="FEBIBILSTEIN",
            source_brand_after="POLMO",
            source_display_brand_after="POLMO",
            new_brand_after="FEBI BILSTEIN",
            new_display_brand_after="FEBI BILSTEIN",
            offers_to_move=(str(move_offer.id),),
            raw_offers_to_move=(str(raw_move.id),),
            source_productprice_ids=tuple(),
        )

        result = self.validator.validate_candidate(candidate)
        self.assertEqual(result.status, AutoDbProductSplitV21Validator.STATUS_CLEAN)
        self.assertEqual(result.blockers, tuple())
        self.assertEqual(result.keep_offer_count, 1)
        self.assertEqual(result.moved_offer_count, 1)
        self.assertEqual(result.expected_source_purchase_from_keep, str(keep_offer.purchase_price))

    def test_unresolved_new_autodb_supplier_blocks(self):
        product = Product.objects.create(
            sku="SKU-V21-UNRESOLVED-AUTODB",
            svom_sku="SVOM-V21-UNRESOLVED-AUTODB",
            article="01111",
            name="Unresolved moved brand autodb",
            slug="v21-unresolved-new-autodb",
            brand=self.brand_polmo,
            category=self.category,
            display_brand_name="POLMO",
            autodb_supplier_id=777,
            autodb_supplier_name="POLMO",
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.gpl,
            product=product,
            supplier_sku="01111",
            currency="UAH",
            purchase_price="400.00",
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
            supplier_sku="FE01111",
            currency="UAH",
            purchase_price="120.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=0,
            lead_time_days=0,
            is_available=False,
        )
        ProductPrice.objects.create(
            product=product,
            currency="UAH",
            purchase_price="400.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="400.00",
            raw_sale_price="450.00",
            final_price="450.00",
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
            price="400.00",
            stock_qty=2,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        SupplierRawOffer.objects.create(
            run=self.run_utr,
            source=self.source_utr,
            supplier=self.utr,
            external_sku="FE01111",
            article="01111",
            normalized_article="01111",
            brand_name="FEBI BILSTEIN",
            normalized_brand="FEBIBILSTEIN",
            product_name="FEBI part",
            price="120.00",
            stock_qty=0,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        candidate = SplitV21Candidate(
            case_label="unresolved_new_autodb",
            sku=str(product.svom_sku or ""),
            source_product_id=str(product.id),
            keep_group="POLMO|01111",
            move_group="FEBIBILSTEIN|01111",
            keep_brand_norm="POLMO",
            move_brand_norm="FEBIBILSTEIN",
            source_brand_after="POLMO",
            source_display_brand_after="POLMO",
            new_brand_after="FEBI BILSTEIN",
            new_display_brand_after="FEBI BILSTEIN",
            offers_to_move=(str(move_offer.id),),
            raw_offers_to_move=tuple(),
            source_productprice_ids=tuple(),
        )
        result = self.validator.validate_candidate(candidate)
        blockers = set(result.blockers)
        self.assertEqual(result.status, AutoDbProductSplitV21Validator.STATUS_BLOCKED)
        self.assertIn("brand_display_conflict_unresolved_new_autodb_supplier", blockers)
        self.assertIn("missing_deterministic_supplier_candidate", blockers)

        planner = AutoDbProductSplitV2Planner()
        plan = planner.plan(
            sku=str(product.svom_sku or ""),
            source_product_id=str(product.id),
            moved_offer_ids=[str(move_offer.id)],
            keep_group="POLMO|01111",
            move_group="FEBIBILSTEIN|01111",
        )
        self.assertIn("brand_display_conflict_unresolved_new_autodb_supplier", set(plan.blockers))

    def test_mann_mahle_case_blocks(self):
        product = Product.objects.create(
            sku="SKU-V21-MANN",
            svom_sku="SVOM-V21-MANN",
            article="KX80D",
            name="Fuel filter",
            slug="v21-mann-source",
            brand=self.brand_mann,
            category=self.category,
            display_brand_name="MANN-FILTER",
            autodb_supplier_id=4,
            autodb_supplier_name="MANN-FILTER",
            is_active=True,
        )
        keep_offer = SupplierOffer.objects.create(
            supplier=self.utr,
            product=product,
            supplier_sku="KX80D",
            currency="UAH",
            purchase_price="481.27",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=0,
            lead_time_days=0,
            is_available=False,
        )
        move_offer = SupplierOffer.objects.create(
            supplier=self.gpl,
            product=product,
            supplier_sku="000000000316268",
            currency="UAH",
            purchase_price="817.00",
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
            purchase_price="817.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="817.00",
            raw_sale_price="898.70",
            final_price="898.70",
        )
        SupplierRawOffer.objects.create(
            run=self.run_utr,
            source=self.source_utr,
            supplier=self.utr,
            external_sku="KX80D",
            article="KX80D",
            normalized_article="KX80D",
            brand_name="MAHLE ORIGINAL",
            normalized_brand="MAHLEORIGINAL",
            product_name="MAHLE fuel filter",
            price="481.27",
            stock_qty=0,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        SupplierRawOffer.objects.create(
            run=self.run_gpl,
            source=self.source_gpl,
            supplier=self.gpl,
            external_sku="000000000316268",
            article="TKX80D",
            normalized_article="TKX80D",
            brand_name="MANN-FILTER",
            normalized_brand="MANNFILTER",
            product_name="MANN filter",
            price="817.00",
            stock_qty=1,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        candidate = SplitV21Candidate(
            case_label="mann_mahle",
            sku=str(product.svom_sku or ""),
            source_product_id=str(product.id),
            keep_group="MAHLEORIGINAL|KX80D",
            move_group="MANNFILTER|KX80D",
            keep_brand_norm="MAHLEORIGINAL",
            move_brand_norm="MANNFILTER",
            source_brand_after="MAHLE ORIGINAL",
            source_display_brand_after="MAHLE ORIGINAL",
            new_brand_after="MANN-FILTER",
            new_display_brand_after="MANN-FILTER",
            offers_to_move=(str(move_offer.id),),
            raw_offers_to_move=tuple(),
            source_productprice_ids=tuple(),
        )
        result = self.validator.validate_candidate(candidate)
        self.assertEqual(result.status, AutoDbProductSplitV21Validator.STATUS_BLOCKED)
        self.assertIn("source_catalog_brand_mismatch_requires_update", set(result.blockers))
        self.assertIn("source_productprice_basis_mismatch", set(result.blockers))
        self.assertIn("brand_and_productprice_basis_mismatch_like_4S5V3O6M6442", result.notes)
        self.assertEqual(result.expected_source_purchase_from_keep, str(keep_offer.purchase_price))

    def test_productprice_basis_mismatch_blocks(self):
        product = Product.objects.create(
            sku="SKU-V21-PRICE",
            svom_sku="SVOM-V21-PRICE",
            article="01111",
            name="POLMO exhaust price mismatch",
            slug="v21-price-mismatch",
            brand=self.brand_polmo,
            category=self.category,
            display_brand_name="POLMO",
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
            supplier_sku="FE01111",
            currency="UAH",
            purchase_price="150.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=0,
            lead_time_days=0,
            is_available=False,
        )
        ProductPrice.objects.create(
            product=product,
            currency="UAH",
            purchase_price="150.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="150.00",
            raw_sale_price="180.00",
            final_price="180.00",
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
        SupplierRawOffer.objects.create(
            run=self.run_utr,
            source=self.source_utr,
            supplier=self.utr,
            external_sku="FE01111",
            article="01111",
            normalized_article="01111",
            brand_name="FEBI BILSTEIN",
            normalized_brand="FEBIBILSTEIN",
            product_name="FEBI part",
            price="150.00",
            stock_qty=0,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        candidate = SplitV21Candidate(
            case_label="price_mismatch",
            sku=str(product.svom_sku or ""),
            source_product_id=str(product.id),
            keep_group="POLMO|01111",
            move_group="FEBIBILSTEIN|01111",
            keep_brand_norm="POLMO",
            move_brand_norm="FEBIBILSTEIN",
            source_brand_after="POLMO",
            source_display_brand_after="POLMO",
            new_brand_after="FEBI BILSTEIN",
            new_display_brand_after="FEBI BILSTEIN",
            offers_to_move=(str(move_offer.id),),
            raw_offers_to_move=tuple(),
            source_productprice_ids=tuple(),
        )
        result = self.validator.validate_candidate(candidate)
        self.assertEqual(result.status, AutoDbProductSplitV21Validator.STATUS_BLOCKED)
        self.assertIn("source_productprice_basis_mismatch", set(result.blockers))
        self.assertEqual(result.expected_source_purchase_from_keep, str(keep_offer.purchase_price))

    def test_brand_display_mismatch_blocks(self):
        product = Product.objects.create(
            sku="SKU-V21-BRAND",
            svom_sku="SVOM-V21-BRAND",
            article="01111",
            name="Brand mismatch sample",
            slug="v21-brand-mismatch",
            brand=self.brand_polmo,
            category=self.category,
            display_brand_name="DAYCO",
            is_active=True,
        )
        move_offer = SupplierOffer.objects.create(
            supplier=self.utr,
            product=product,
            supplier_sku="FE01111",
            currency="UAH",
            purchase_price="120.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=0,
            lead_time_days=0,
            is_available=False,
        )
        SupplierOffer.objects.create(
            supplier=self.gpl,
            product=product,
            supplier_sku="01111",
            currency="UAH",
            purchase_price="400.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=2,
            lead_time_days=0,
            is_available=True,
        )
        ProductPrice.objects.create(
            product=product,
            currency="UAH",
            purchase_price="400.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="400.00",
            raw_sale_price="450.00",
            final_price="450.00",
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
            price="400.00",
            stock_qty=2,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        SupplierRawOffer.objects.create(
            run=self.run_utr,
            source=self.source_utr,
            supplier=self.utr,
            external_sku="FE01111",
            article="01111",
            normalized_article="01111",
            brand_name="FEBI BILSTEIN",
            normalized_brand="FEBIBILSTEIN",
            product_name="FEBI part",
            price="120.00",
            stock_qty=0,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        candidate = SplitV21Candidate(
            case_label="display_mismatch",
            sku=str(product.svom_sku or ""),
            source_product_id=str(product.id),
            keep_group="POLMO|01111",
            move_group="FEBIBILSTEIN|01111",
            keep_brand_norm="POLMO",
            move_brand_norm="FEBIBILSTEIN",
            source_brand_after="POLMO",
            source_display_brand_after="POLMO",
            new_brand_after="FEBI BILSTEIN",
            new_display_brand_after="FEBI BILSTEIN",
            offers_to_move=(str(move_offer.id),),
            raw_offers_to_move=tuple(),
            source_productprice_ids=tuple(),
        )
        result = self.validator.validate_candidate(candidate)
        self.assertEqual(result.status, AutoDbProductSplitV21Validator.STATUS_BLOCKED)
        self.assertIn("source_display_brand_mismatch_requires_update", set(result.blockers))

    def test_supplier_raw_offer_mismatch_blocks(self):
        product = Product.objects.create(
            sku="SKU-V21-RAW",
            svom_sku="SVOM-V21-RAW",
            article="01111",
            name="Raw mismatch sample",
            slug="v21-raw-mismatch",
            brand=self.brand_polmo,
            category=self.category,
            display_brand_name="POLMO",
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.gpl,
            product=product,
            supplier_sku="01111",
            currency="UAH",
            purchase_price="400.00",
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
            supplier_sku="FE01111",
            currency="UAH",
            purchase_price="120.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=0,
            lead_time_days=0,
            is_available=False,
        )
        ProductPrice.objects.create(
            product=product,
            currency="UAH",
            purchase_price="400.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="400.00",
            raw_sale_price="450.00",
            final_price="450.00",
        )
        # Intentionally no raw row for moved offer
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
            price="400.00",
            stock_qty=2,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        candidate = SplitV21Candidate(
            case_label="raw_mismatch",
            sku=str(product.svom_sku or ""),
            source_product_id=str(product.id),
            keep_group="POLMO|01111",
            move_group="FEBIBILSTEIN|01111",
            keep_brand_norm="POLMO",
            move_brand_norm="FEBIBILSTEIN",
            source_brand_after="POLMO",
            source_display_brand_after="POLMO",
            new_brand_after="FEBI BILSTEIN",
            new_display_brand_after="FEBI BILSTEIN",
            offers_to_move=(str(move_offer.id),),
            raw_offers_to_move=tuple(),
            source_productprice_ids=tuple(),
        )
        result = self.validator.validate_candidate(candidate)
        self.assertEqual(result.status, AutoDbProductSplitV21Validator.STATUS_BLOCKED)
        self.assertIn("raw_offer_mismatch_for_moved_offer", set(result.blockers))

    def test_dry_run_has_no_writes(self):
        product = Product.objects.create(
            sku="SKU-V21-NOWRITE",
            svom_sku="SVOM-V21-NOWRITE",
            article="01111",
            name="No write sample",
            slug="v21-no-write",
            brand=self.brand_polmo,
            category=self.category,
            display_brand_name="POLMO",
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.gpl,
            product=product,
            supplier_sku="01111",
            currency="UAH",
            purchase_price="200.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=1,
            lead_time_days=0,
            is_available=True,
        )
        move_offer = SupplierOffer.objects.create(
            supplier=self.utr,
            product=product,
            supplier_sku="FE01111",
            currency="UAH",
            purchase_price="100.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=0,
            lead_time_days=0,
            is_available=False,
        )
        ProductPrice.objects.create(
            product=product,
            currency="UAH",
            purchase_price="200.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="200.00",
            raw_sale_price="220.00",
            final_price="220.00",
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
            price="200.00",
            stock_qty=1,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        SupplierRawOffer.objects.create(
            run=self.run_utr,
            source=self.source_utr,
            supplier=self.utr,
            external_sku="FE01111",
            article="01111",
            normalized_article="01111",
            brand_name="FEBI BILSTEIN",
            normalized_brand="FEBIBILSTEIN",
            product_name="FEBI part",
            price="100.00",
            stock_qty=0,
            lead_time_days=0,
            matched_product=product,
            is_valid=True,
        )
        candidate = SplitV21Candidate(
            case_label="no_write",
            sku=str(product.svom_sku or ""),
            source_product_id=str(product.id),
            keep_group="POLMO|01111",
            move_group="FEBIBILSTEIN|01111",
            keep_brand_norm="POLMO",
            move_brand_norm="FEBIBILSTEIN",
            source_brand_after="POLMO",
            source_display_brand_after="POLMO",
            new_brand_after="FEBI BILSTEIN",
            new_display_brand_after="FEBI BILSTEIN",
            offers_to_move=(str(move_offer.id),),
            raw_offers_to_move=tuple(),
            source_productprice_ids=tuple(),
        )

        before = {
            "product": Product.objects.count(),
            "offer": SupplierOffer.objects.count(),
            "raw": SupplierRawOffer.objects.count(),
            "price": ProductPrice.objects.count(),
            "fitment": ProductFitment.objects.count(),
        }
        _ = self.validator.validate_candidate(candidate)
        after = {
            "product": Product.objects.count(),
            "offer": SupplierOffer.objects.count(),
            "raw": SupplierRawOffer.objects.count(),
            "price": ProductPrice.objects.count(),
            "fitment": ProductFitment.objects.count(),
        }
        self.assertEqual(before, after)
