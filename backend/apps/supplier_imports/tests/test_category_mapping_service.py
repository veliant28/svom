from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.supplier_imports.services import SupplierRawOfferCategoryMappingService


class SupplierRawOfferCategoryMappingServiceTests(TestCase):
    def setUp(self):
        self.root_category = Category.objects.create(name="Гальмівна система", slug="halmivna-systema", is_active=True)
        self.leaf_category = Category.objects.create(name="Гальмівні колодки", slug="halmivni-kolodky", parent=self.root_category, is_active=True)
        self.hub_bearing_category = Category.objects.create(name="Підшипник маточини", slug="pidshypnyk-matochyny", parent=self.root_category, is_active=True)
        self.air_filter_category = Category.objects.create(name="Повітряний фільтр", slug="povitrianyi-filtr", parent=self.root_category, is_active=True)
        self.cabin_filter_category = Category.objects.create(name="Фільтр салону", slug="filtr-salonu", parent=self.root_category, is_active=True)
        self.gearbox_bearing_category = Category.objects.create(name="Підшипник КПП", slug="pidshypnyk-kpp", parent=self.root_category, is_active=True)
        self.cv_joint_category = Category.objects.create(name="ШРУС", slug="shrus", parent=self.root_category, is_active=True)
        self.brand = Brand.objects.create(name="TEST", slug="test", is_active=True)
        self.product = Product.objects.create(
            sku="TEST-001",
            article="TEST-001",
            name="Test pads",
            slug="test-pads",
            brand=self.brand,
            category=self.leaf_category,
            is_active=True,
        )

        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )
        self.run = ImportRun.objects.create(source=self.source, status=ImportRun.STATUS_SUCCESS, trigger="test")
        self.service = SupplierRawOfferCategoryMappingService()

    def _raw_offer(self, **kwargs) -> SupplierRawOffer:
        defaults = {
            "run": self.run,
            "source": self.source,
            "supplier": self.supplier,
            "external_sku": "SKU-1",
            "article": "SKU-1",
            "normalized_article": "SKU1",
            "brand_name": "TEST",
            "normalized_brand": "TEST",
            "product_name": "Гальмівні колодки передні",
            "currency": "UAH",
            "price": Decimal("100.00"),
            "stock_qty": 1,
            "is_valid": False,
            "skip_reason": "unmatched",
            "raw_payload": {},
        }
        defaults.update(kwargs)
        return SupplierRawOffer.objects.create(**defaults)

    def test_uses_matched_product_category_as_high_confidence(self):
        raw_offer = self._raw_offer(matched_product=self.product)
        result = self.service.apply_auto_mapping(raw_offer=raw_offer)
        raw_offer.refresh_from_db()

        self.assertEqual(result.status, SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED)
        self.assertEqual(raw_offer.category_mapping_reason, SupplierRawOffer.CATEGORY_MAPPING_REASON_FROM_PRODUCT)
        self.assertEqual(raw_offer.mapped_category_id, self.leaf_category.id)

    def test_exact_supplier_category_signal_maps_automatically(self):
        raw_offer = self._raw_offer(
            raw_payload={
                "Категорія": "Гальмівні колодки",
            }
        )
        result = self.service.apply_auto_mapping(raw_offer=raw_offer)
        raw_offer.refresh_from_db()

        self.assertEqual(result.status, SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED)
        self.assertEqual(raw_offer.mapped_category_id, self.leaf_category.id)

    def test_unknown_signal_stays_unmapped(self):
        raw_offer = self._raw_offer(
            product_name="Запчастина без явної категорії",
            raw_payload={"Category": "UNKNOWN VALUE"},
        )
        result = self.service.apply_auto_mapping(raw_offer=raw_offer)
        raw_offer.refresh_from_db()

        self.assertEqual(result.status, SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED)
        self.assertIsNone(raw_offer.mapped_category_id)

    def test_force_mode_assigns_category_to_unmapped(self):
        raw_offer = self._raw_offer(
            product_name="Дуже рідкісна деталь без сигнальних ключів",
            raw_payload={"key": "value"},
        )
        result = self.service.apply_auto_mapping(raw_offer=raw_offer, force_map_all=True)
        raw_offer.refresh_from_db()

        self.assertIsNotNone(raw_offer.mapped_category_id)
        self.assertNotEqual(result.status, SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED)

    def test_recheck_risky_mapping_remaps_conflicting_hub_bearing(self):
        raw_offer = self._raw_offer(
            product_name="р-к ШРКШ з пильником",
            mapped_category=self.hub_bearing_category,
            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
            category_mapping_reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TITLE_SIGNATURE,
            category_mapping_confidence=Decimal("0.950"),
        )
        result = self.service.recheck_risky_mapping(raw_offer=raw_offer)
        raw_offer.refresh_from_db()

        self.assertTrue(result.updated)
        self.assertEqual(raw_offer.category_mapping_status, SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW)
        self.assertEqual(raw_offer.category_mapping_reason, SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REMAP)
        self.assertEqual(raw_offer.mapped_category_id, self.cv_joint_category.id)

    def test_recheck_risky_mapping_does_not_overwrite_manual(self):
        raw_offer = self._raw_offer(
            product_name="р-к ШРКШ з пильником",
            mapped_category=self.hub_bearing_category,
            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
            category_mapping_reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_MANUAL,
            category_mapping_confidence=Decimal("1.000"),
        )
        result = self.service.recheck_risky_mapping(raw_offer=raw_offer)
        raw_offer.refresh_from_db()

        self.assertFalse(result.updated)
        self.assertTrue(result.skipped_manual)
        self.assertEqual(raw_offer.category_mapping_status, SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED)

    def test_selective_guardrail_recheck_remaps_air_filter_from_cabin_to_auto(self):
        raw_offer = self._raw_offer(
            product_name="Фильтр воздушный двигателя",
            mapped_category=self.cabin_filter_category,
            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
            category_mapping_reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_SIGNAL_LEARNING,
            category_mapping_confidence=Decimal("0.910"),
        )
        result = self.service.recheck_guardrail_mapping(
            raw_offer=raw_offer,
            allowed_guardrail_codes={"cabin_filter_vs_air_filter"},
        )
        raw_offer.refresh_from_db()

        self.assertTrue(result.updated)
        self.assertEqual(raw_offer.mapped_category_id, self.air_filter_category.id)
        self.assertEqual(raw_offer.category_mapping_status, SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED)
        self.assertEqual(raw_offer.category_mapping_reason, SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REMAP)
        self.assertGreaterEqual(raw_offer.category_mapping_confidence, Decimal("0.945"))

    def test_selective_guardrail_recheck_remaps_gearbox_bearing_from_hub_to_auto(self):
        raw_offer = self._raw_offer(
            product_name="Подшипник КПП ремкомплект",
            mapped_category=self.hub_bearing_category,
            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
            category_mapping_reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_SIGNAL_LEARNING,
            category_mapping_confidence=Decimal("0.900"),
        )
        result = self.service.recheck_guardrail_mapping(
            raw_offer=raw_offer,
            allowed_guardrail_codes={"hub_bearing_vs_gearbox_bearing"},
        )
        raw_offer.refresh_from_db()

        self.assertTrue(result.updated)
        self.assertEqual(raw_offer.mapped_category_id, self.gearbox_bearing_category.id)
        self.assertEqual(raw_offer.category_mapping_status, SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED)
        self.assertEqual(raw_offer.category_mapping_reason, SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REMAP)
        self.assertGreaterEqual(raw_offer.category_mapping_confidence, Decimal("0.940"))
