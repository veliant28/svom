from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from apps.autodb.services.matching.deterministic_brand_binding import (
    AutoDbDeterministicBrandBindingService,
    DeterministicBrandNormalizer,
    SupplierEntry,
)
from apps.catalog.models import Brand, Category, Product


class DeterministicBrandNormalizerTests(SimpleTestCase):
    def setUp(self):
        self.normalizer = DeterministicBrandNormalizer()

    def test_lemforder_maps_to_lemfoerder(self):
        variants = self.normalizer.variants("LEMFÖRDER")
        self.assertIn("LEMFORDER", variants)
        self.assertIn("LEMFOERDER", variants)

    def test_lesjofors_maps_to_lesjoefors(self):
        variants = self.normalizer.variants("LESJÖFORS")
        self.assertIn("LESJOFORS", variants)
        self.assertIn("LESJOEFORS", variants)

    def test_lobro_maps_to_loebro(self):
        variants = self.normalizer.variants("LÖBRO")
        self.assertIn("LOBRO", variants)
        self.assertIn("LOEBRO", variants)

    def test_nural_maps_to_nueral(self):
        variants = self.normalizer.variants("NÜRAL")
        self.assertIn("NURAL", variants)
        self.assertIn("NUERAL", variants)

    def test_durer_maps_to_umlaut_form(self):
        variants = self.normalizer.variants("DÜRER")
        self.assertIn("DURER", variants)

    def test_eberspaecher_maps_to_umlaut_form(self):
        variants = self.normalizer.variants("EBERSPÄCHER")
        self.assertIn("EBERSPACHER", variants)
        self.assertIn("EBERSPAECHER", variants)

    def test_kale_oto_radyator_maps_to_umlaut_form(self):
        variants = self.normalizer.variants("KALE OTO RADYATÖR")
        self.assertIn("KALEOTORADYATOR", variants)

    def test_neolux_trademark_variants_collapse(self):
        variants = self.normalizer.variants("NEOLUX®")
        self.assertIn("NEOLUX", variants)
        self.assertIn("NEOLUXR", self.normalizer.variants("NEOLUX R"))

    def test_schlutter_maps_to_schluetter(self):
        variants = self.normalizer.variants("SCHLÜTTER TURBOLADER")
        self.assertIn("SCHLUTTERTURBOLADER", variants)
        self.assertIn("SCHLUETTERTURBOLADER", variants)

    def test_spahn_gluhlampen_maps_to_gluehlampen(self):
        variants = self.normalizer.variants("SPAHN GLÜHLAMPEN")
        self.assertIn("SPAHNGLUHLAMPEN", variants)
        self.assertIn("SPAHNGLUEHLAMPEN", variants)


class DeterministicBrandDecisionTests(SimpleTestCase):
    def setUp(self):
        self.service = AutoDbDeterministicBrandBindingService()

    def test_ambiguous_candidates_are_blocked(self):
        suppliers = [
            SupplierEntry(1, "CTR", "CTR", 10, tuple(sorted(self.service.normalizer.variants("CTR")))),
            SupplierEntry(2, "CTR", "CTR", 10, tuple(sorted(self.service.normalizer.variants("CTR")))),
        ]
        supplier_by_id = {1: suppliers[0], 2: suppliers[1]}
        index = self.service._build_supplier_variant_index(suppliers)
        brand_stats = {
            10: {
                "brand_id": 10,
                "brand_name": "CTR",
                "product_count": 5,
                "missing_count": 5,
                "manually_locked_count": 0,
                "supplier_counts": {},
                "sample_skus": ["SKU-1"],
            }
        }

        rows, _ = self.service._build_candidates(
            suppliers=suppliers,
            supplier_by_id=supplier_by_id,
            variant_index=index,
            alias_map={},
            brand_stats=brand_stats,
        )

        self.assertEqual(rows[0]["decision"], "skipped_split_or_unsafe")

    def test_existing_different_supplier_is_blocked(self):
        supplier = SupplierEntry(100, "LEMFÖRDER", "LEMFORDER", 100, tuple(sorted(self.service.normalizer.variants("LEMFÖRDER"))))
        index = self.service._build_supplier_variant_index([supplier])
        rows, _ = self.service._build_candidates(
            suppliers=[supplier],
            supplier_by_id={100: supplier},
            variant_index=index,
            alias_map={},
            brand_stats={
                1: {
                    "brand_id": 1,
                    "brand_name": "LEMFORDER",
                    "product_count": 4,
                    "missing_count": 1,
                    "manually_locked_count": 0,
                    "supplier_counts": {999: 3},
                    "sample_skus": ["SKU-1"],
                }
            },
        )
        self.assertEqual(rows[0]["decision"], "blocked_existing_different_supplier")

    def test_manually_locked_only_is_skipped(self):
        supplier = SupplierEntry(100, "LEMFÖRDER", "LEMFORDER", 100, tuple(sorted(self.service.normalizer.variants("LEMFÖRDER"))))
        index = self.service._build_supplier_variant_index([supplier])
        rows, _ = self.service._build_candidates(
            suppliers=[supplier],
            supplier_by_id={100: supplier},
            variant_index=index,
            alias_map={},
            brand_stats={
                1: {
                    "brand_id": 1,
                    "brand_name": "LEMFORDER",
                    "product_count": 3,
                    "missing_count": 3,
                    "manually_locked_count": 3,
                    "supplier_counts": {},
                    "sample_skus": ["SKU-1"],
                }
            },
        )
        self.assertEqual(rows[0]["decision"], "skipped_manual_locked_only")


class DeterministicBrandApplySafetyTests(TestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        self.service = AutoDbDeterministicBrandBindingService()
        self.brand = Brand.objects.create(name="LEMFORDER", slug="lemforder", is_active=True)
        self.category = Category.objects.create(name="Cat", slug="cat", is_active=True)
        self.product = Product.objects.create(
            sku="SKU-1",
            article="A1",
            name="P1",
            slug="p1",
            brand=self.brand,
            category=self.category,
            autodb_article_number="A1",
            autodb_article_key="100:A1",
            autodb_supplier_id=None,
            brand_manually_locked=False,
        )

    def test_apply_does_not_touch_article_link_fields(self):
        rows = [
            {
                "catalog_brand_id": str(self.brand.id),
                "catalog_brand_name": "LEMFORDER",
                "autodb_supplier_id": "100",
                "autodb_supplier_description": "LEMFÖRDER",
                "alias_action": "would_create",
            }
        ]

        self.service._apply(rows, {})

        self.product.refresh_from_db()
        self.assertEqual(self.product.autodb_article_number, "A1")
        self.assertEqual(self.product.autodb_article_key, "100:A1")
        self.assertEqual(self.product.autodb_supplier_id, 100)
