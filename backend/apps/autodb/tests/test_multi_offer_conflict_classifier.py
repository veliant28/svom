from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase

from apps.autodb.models import AutoDbMatchJob
from apps.autodb.services.matching.job_builder import AutoDbMatchJobBuilder
from apps.autodb.services.matching.multi_offer_conflict_classifier import (
    AutoDbMultiOfferConflictClassifier,
    AutoDbMultiOfferConflictResult,
)
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer


class FakeBrandResolver:
    def __init__(self, mapping: dict[str, int]):
        self.mapping = {key.upper(): value for key, value in mapping.items()}

    def resolve(self, raw_brand: str, supplier_code: str, product_autodb_supplier_id=None):  # noqa: ARG002
        key = str(raw_brand or "").upper().strip()
        supplier_id = self.mapping.get(key)
        return SimpleNamespace(supplier_id=supplier_id, supplier_name=key if supplier_id else "")


class AutoDbMultiOfferConflictClassifierTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.brand = Brand.objects.create(name="FEBI BILSTEIN", slug="febi-bilstein", is_active=True)
        self.category = Category.objects.create(name="Exhaust", slug="exhaust", is_active=True)
        self.product = Product.objects.create(
            sku="SKU-MULTI-1",
            article="A1",
            name="POLMO Exhaust Pipe",
            slug="polmo-exhaust-pipe",
            brand=self.brand,
            category=self.category,
            display_brand_name="FEBI BILSTEIN",
            autodb_supplier_id=101,
            autodb_supplier_name="FEBI BILSTEIN",
            is_active=True,
        )
        self.gpl = Supplier.objects.create(name="GPL", code="gpl")
        self.utr = Supplier.objects.create(name="UTR", code="utr")
        self.classifier = AutoDbMultiOfferConflictClassifier(
            brand_resolver=FakeBrandResolver({"FEBI BILSTEIN": 101, "POLMO": 202})
        )

    def _offer(self, *, supplier: Supplier, sku: str, price: str, stock: int) -> SupplierOffer:
        return SupplierOffer.objects.create(
            supplier=supplier,
            product=self.product,
            supplier_sku=sku,
            currency="UAH",
            purchase_price=price,
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=stock,
            lead_time_days=0,
            is_available=True,
        )

    def _raw(self, *, brand: str, article: str, title: str):
        return SimpleNamespace(
            brand_name=brand,
            article=article,
            raw_payload={
                "Бренд": brand,
                "Артикул ТД": article,
                "name": title,
            },
        )

    def test_gpl_utr_different_brands_is_brand_conflict(self):
        offer_a = self._offer(supplier=self.gpl, sku="A-1", price="100.00", stock=3)
        offer_b = self._offer(supplier=self.utr, sku="A-1", price="110.00", stock=2)
        raw_map = {
            (str(self.product.id), str(self.gpl.id)): self._raw(brand="FEBI BILSTEIN", article="A-1", title="FEBI item"),
            (str(self.product.id), str(self.utr.id)): self._raw(brand="POLMO", article="A-1", title="POLMO item"),
        }

        result = self.classifier.classify_product(product=self.product, offers=[offer_a, offer_b], raw_offer_map=raw_map)

        self.assertEqual(result.status, "multi_offer_brand_conflict")
        self.assertIn("multi_offer_brand_conflict", result.conflict_reasons)
        self.assertFalse(result.allow_auto_matching)

    def test_price_ratio_gt_5_is_extreme(self):
        offer_a = self._offer(supplier=self.gpl, sku="A-1", price="100.00", stock=3)
        offer_b = self._offer(supplier=self.utr, sku="A-1", price="900.00", stock=2)
        raw_map = {
            (str(self.product.id), str(self.gpl.id)): self._raw(brand="FEBI BILSTEIN", article="A-1", title="FEBI item"),
            (str(self.product.id), str(self.utr.id)): self._raw(brand="FEBI BILSTEIN", article="A-1", title="FEBI item"),
        }

        result = self.classifier.classify_product(product=self.product, offers=[offer_a, offer_b], raw_offer_map=raw_map)

        self.assertTrue(result.price_ratio_extreme)
        self.assertIn("multi_offer_price_ratio_extreme", result.conflict_reasons)

    def test_title_brand_conflict_detected(self):
        offer_a = self._offer(supplier=self.gpl, sku="A-1", price="100.00", stock=3)
        offer_b = self._offer(supplier=self.utr, sku="A-1", price="101.00", stock=2)
        raw_map = {
            (str(self.product.id), str(self.gpl.id)): self._raw(brand="FEBI BILSTEIN", article="A-1", title="FEBI item"),
            (str(self.product.id), str(self.utr.id)): self._raw(brand="FEBI BILSTEIN", article="A-1", title="FEBI item"),
        }

        result = self.classifier.classify_product(product=self.product, offers=[offer_a, offer_b], raw_offer_map=raw_map)

        self.assertTrue(result.title_brand_conflict)
        self.assertIn("title_brand_conflict", result.conflict_reasons)

    def test_trusted_link_with_offer_conflict_maps_to_needs_review_trusted_conflict(self):
        offer_a = self._offer(supplier=self.gpl, sku="A-1", price="100.00", stock=3)
        offer_b = self._offer(supplier=self.utr, sku="B-2", price="120.00", stock=2)
        raw_map = {
            (str(self.product.id), str(self.gpl.id)): self._raw(brand="POLMO", article="A-1", title="POLMO item"),
            (str(self.product.id), str(self.utr.id)): self._raw(brand="POLMO", article="B-2", title="POLMO item"),
        }
        AutoDbProductLinkQuality.objects.create(
            product=self.product,
            autodb_article_key="101:A1",
            autodb_supplier_id=101,
            autodb_article_number="A1",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="test",
            evidence={},
        )

        by_product = self.classifier.classify_from_offers(offers=[offer_a, offer_b], raw_offer_map=raw_map)
        result = by_product[str(self.product.id)]

        self.assertTrue(result.trusted_link_conflict)
        self.assertEqual(result.reason_code, "needs_review_trusted_conflict")
        self.assertEqual(result.recommended_job_status, AutoDbMatchJob.STATUS_NEEDS_REVIEW)

    def test_clean_multi_offer_same_brand_article_allowed(self):
        offer_a = self._offer(supplier=self.gpl, sku="A-1", price="100.00", stock=3)
        offer_b = self._offer(supplier=self.utr, sku="A-1", price="105.00", stock=2)
        raw_map = {
            (str(self.product.id), str(self.gpl.id)): self._raw(brand="FEBI BILSTEIN", article="A-1", title="FEBI item"),
            (str(self.product.id), str(self.utr.id)): self._raw(brand="FEBI BILSTEIN", article="A-1", title="FEBI item"),
        }
        self.product.name = "FEBI BILSTEIN Exhaust Pipe"
        self.product.save(update_fields=["name", "updated_at"])

        result = self.classifier.classify_product(product=self.product, offers=[offer_a, offer_b], raw_offer_map=raw_map)

        self.assertEqual(result.status, "multi_offer_ok")
        self.assertTrue(result.allow_auto_matching)
        self.assertEqual(result.reason_code, "")


class AutoDbMatchJobBuilderMultiOfferGuardTests(TestCase):
    databases = {"default"}

    def setUp(self):
        brand = Brand.objects.create(name="FEBI BILSTEIN", slug="febi-guard", is_active=True)
        category = Category.objects.create(name="Suspension", slug="suspension-guard", is_active=True)
        self.product = Product.objects.create(
            sku="SKU-GUARD-1",
            article="X1",
            name="Product Guard",
            slug="product-guard",
            brand=brand,
            category=category,
            is_active=True,
        )
        gpl = Supplier.objects.create(name="GPL", code="gpl")
        self.offer = SupplierOffer.objects.create(
            supplier=gpl,
            product=self.product,
            supplier_sku="X1",
            currency="UAH",
            purchase_price="100.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=5,
            lead_time_days=0,
            is_available=True,
        )
        self.stub_result = AutoDbMultiOfferConflictResult(
            product_id=str(self.product.id),
            offer_count=2,
            status="likely_bad_merge",
            reason_code="skipped_multi_offer_conflict",
            allow_auto_matching=False,
            recommended_job_status=AutoDbMatchJob.STATUS_REJECTED,
            conflict_reasons=("likely_bad_merge",),
            supplier_codes=("gpl", "utr"),
            offer_brand_norms=("FEBIBILSTEIN", "POLMO"),
            offer_article_norms=("01111", "851111"),
            candidate_supplier_ids=(101, 202),
            trusted_supplier_ids=(),
            price_ratio="18.0",
            brand_conflict_between_offers=True,
            article_conflict_between_offers=True,
            title_brand_conflict=False,
            supplier_code_conflict_gpl_utr=True,
            price_spread_high=True,
            price_ratio_extreme=True,
            product_autodb_supplier_conflict=False,
            trusted_link_conflict=False,
            likely_bad_merge=True,
            split_product_candidate=False,
        )

    def test_builder_excludes_likely_bad_merge_in_dry_run(self):
        classifier = SimpleNamespace(classify_from_offers=lambda offers, raw_offer_map=None: {str(self.product.id): self.stub_result})  # noqa: ARG005
        article_resolver = SimpleNamespace(
            resolve=lambda **kwargs: SimpleNamespace(  # noqa: ARG005
                is_usable=True,
                source_type="payload_manufacturer_article",
                article_value="X1",
                canonical_article="X1",
                reason="",
                confidence=1.0,
            )
        )
        builder = AutoDbMatchJobBuilder(
            multi_offer_classifier=classifier,
            article_resolver=article_resolver,
            brand_resolver=FakeBrandResolver({"FEBI BILSTEIN": 101}),
        )
        before = {
            "products": Product.objects.count(),
            "offers": SupplierOffer.objects.count(),
            "prices": ProductPrice.objects.count(),
            "jobs": AutoDbMatchJob.objects.count(),
        }

        rows = builder.build_jobs(supplier_code="gpl", limit=10, dry_run=True)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, AutoDbMatchJob.STATUS_REJECTED)
        self.assertEqual(rows[0].reason, "skipped_multi_offer_conflict")
        self.assertEqual(
            {
                "products": Product.objects.count(),
                "offers": SupplierOffer.objects.count(),
                "prices": ProductPrice.objects.count(),
                "jobs": AutoDbMatchJob.objects.count(),
            },
            before,
        )
