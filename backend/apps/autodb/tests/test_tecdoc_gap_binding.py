from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from apps.autodb.services.matching.tecdoc_gap_binding import AutoDbTecdocGapBindingService
from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier, SupplierOffer


class TecdocGapBindingClassifierTests(SimpleTestCase):
    def setUp(self):
        self.service = AutoDbTecdocGapBindingService()
        self.service._sample_products = lambda **kwargs: ("", "")  # type: ignore[assignment]

    def test_empty_normalized_brand_is_invalid_brand_value(self):
        self.assertTrue(self.service._is_invalid_brand_value(raw_brand="", normalized=""))

    def test_ugorshchina_is_invalid_brand_value(self):
        self.assertTrue(self.service._is_invalid_brand_value(raw_brand="Угорщина", normalized=""))

    def test_udalennye_is_invalid_brand_value(self):
        self.assertTrue(self.service._is_invalid_brand_value(raw_brand="Удаленные", normalized=""))

    def test_local_clean_deterministic_candidate(self):
        suppliers = {101: {"description": "FEBI BILSTEIN", "nbrofarticles": 100, "matchcode": "FEBI"}}
        index = {"FEBIBILSTEIN": {101}}
        rows = self.service._local_candidate_search(
            tecdoc_rows=[
                {
                    "supplier_code": "gpl",
                    "raw_brand": "FEBI BILSTEIN",
                    "normalized_raw_brand": "FEBIBILSTEIN",
                    "product_count": 10,
                    "stock_gt_0_count": 5,
                    "product_price_count": 10,
                }
            ],
            suppliers=suppliers,
            supplier_by_variant=index,
        )
        self.assertEqual(rows[0]["classification"], "local_clean_candidate")

    def test_local_ambiguous_candidate(self):
        suppliers = {
            101: {"description": "CTR", "nbrofarticles": 100, "matchcode": "CTR"},
            202: {"description": "CTR KOREA", "nbrofarticles": 50, "matchcode": "CTR"},
        }
        index = {"CTR": {101, 202}}
        rows = self.service._local_candidate_search(
            tecdoc_rows=[
                {
                    "supplier_code": "gpl",
                    "raw_brand": "CTR",
                    "normalized_raw_brand": "CTR",
                    "product_count": 10,
                    "stock_gt_0_count": 5,
                    "product_price_count": 10,
                }
            ],
            suppliers=suppliers,
            supplier_by_variant=index,
        )
        self.assertEqual(rows[0]["classification"], "local_ambiguous_candidate")


class TecdocGapBindingCandidateSafetyTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.service = AutoDbTecdocGapBindingService()
        self.service._supplier_name_by_id = lambda supplier_id: f"SUP-{supplier_id}"  # type: ignore[assignment]
        self.brand = Brand.objects.create(name="TESTBRAND", slug="testbrand", is_active=True)
        self.category = Category.objects.create(name="Cat", slug="cat", is_active=True)
        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)

    def _product(self, *, sku: str, supplier_id: int | None):
        product = Product.objects.create(
            sku=sku,
            article="A1",
            name=f"Product {sku}",
            slug=f"slug-{sku.lower()}",
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=supplier_id,
            brand_manually_locked=False,
        )
        SupplierOffer.objects.create(
            supplier=self.supplier,
            product=product,
            supplier_sku=f"SUP-{sku}",
            currency="UAH",
            purchase_price="10.00",
            stock_qty=1,
            lead_time_days=0,
            is_available=True,
        )
        return product

    def test_existing_different_autodb_supplier_is_blocked(self):
        self._product(sku="SKU-1", supplier_id=999)
        rows = self.service._build_apply_candidate_set(
            [
                {
                    "supplier_code": "gpl",
                    "raw_brand": "TESTBRAND",
                    "normalized_raw_brand": "TESTBRAND",
                    "local_candidate_supplier_ids": "100",
                    "classification": "local_clean_candidate",
                }
            ]
        )
        self.assertEqual(rows[0]["decision"], "blocked_existing_different_supplier")
