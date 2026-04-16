from django.test import TestCase

from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportSource, SupplierBrandAlias
from apps.supplier_imports.services import BrandAliasResolverService


class BrandAliasResolverServiceTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
        )

    def test_supplier_alias_is_resolved_to_canonical_brand(self):
        SupplierBrandAlias.objects.create(
            source=self.source,
            supplier=self.supplier,
            supplier_brand_alias="MAHLE - KNECHT",
            canonical_brand_name="MAHLE",
            is_active=True,
            priority=200,
        )

        result = BrandAliasResolverService().resolve(
            brand_name="MAHLE - KNECHT",
            source=self.source,
            supplier=self.supplier,
        )

        self.assertEqual(result.canonical_brand, "MAHLE")
        self.assertEqual(result.normalized_brand, "MAHLE")
        self.assertIsNotNone(result.alias_id)

    def test_no_alias_keeps_normalized_input(self):
        result = BrandAliasResolverService().resolve(
            brand_name="Aral GmbH",
            source=self.source,
            supplier=self.supplier,
        )

        self.assertEqual(result.normalized_brand, "ARALGMBH")
        self.assertIsNone(result.alias_id)
