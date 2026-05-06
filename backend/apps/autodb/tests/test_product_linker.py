from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.autodb.services.article_lookup import ArticleLookupResult
from apps.autodb.services.product_linker import AutoDbProductLinkService
from apps.catalog.models import Product


class AutoDbProductLinkServiceTests(SimpleTestCase):
    def test_product_model_has_bridge_fields_without_fk(self):
        autodb_article_field = Product._meta.get_field("autodb_article_id")
        autodb_supplier_field = Product._meta.get_field("autodb_supplier_id")
        self.assertFalse(autodb_article_field.is_relation)
        self.assertFalse(autodb_supplier_field.is_relation)
        self.assertEqual(Product._meta.get_field("autodb_article_number").get_internal_type(), "CharField")
        self.assertEqual(Product._meta.get_field("autodb_article_key").get_internal_type(), "CharField")
        self.assertEqual(Product._meta.get_field("normalized_brand").get_internal_type(), "CharField")
        self.assertEqual(Product._meta.get_field("normalized_article").get_internal_type(), "CharField")

    def test_link_product_saves_autodb_ids(self):
        lookup_service = Mock()
        lookup_service.lookup.return_value = ArticleLookupResult(
            found=True,
            normalized_brand="BOSCH",
            normalized_article="W71295",
            supplier_id=15,
            article_key="15:W712/95",
            article_id=88,
            canonical_article_number="W712/95",
            canonical_brand="BOSCH",
            supplier_source="local",
            article_source="local",
        )
        service = AutoDbProductLinkService(lookup_service=lookup_service)

        product = SimpleNamespace(
            id="p1",
            normalized_brand="",
            normalized_article="",
            autodb_supplier_id=None,
            autodb_article_id=None,
            autodb_article_number="",
            autodb_article_key="",
            catalog_source="",
            save=Mock(),
        )

        result = service.link_product(product=product, brand_name="Bosch", article="W712/95")

        self.assertTrue(result.linked)
        self.assertEqual(product.autodb_supplier_id, 15)
        self.assertEqual(product.autodb_article_id, 88)
        self.assertEqual(product.autodb_article_number, "W712/95")
        self.assertEqual(product.autodb_article_key, "15:W712/95")
        self.assertEqual(product.catalog_source, Product.CATALOG_SOURCE_AUTODB_PRO)
        self.assertEqual(result.link_status, "linked")
        product.save.assert_called_once()

    def test_link_product_with_lookup_dry_run_does_not_save(self):
        lookup_service = Mock()
        service = AutoDbProductLinkService(lookup_service=lookup_service)
        lookup = ArticleLookupResult(
            found=True,
            normalized_brand="AUTEX",
            normalized_article="820099",
            supplier_id=300,
            article_key="300:820099",
            article_id=None,
            canonical_article_number="820099",
            canonical_brand="AUTEX",
            supplier_source="local",
            article_source="local",
        )
        product = SimpleNamespace(
            id="p-dry",
            normalized_brand="",
            normalized_article="",
            autodb_supplier_id=None,
            autodb_article_id=None,
            autodb_article_number="",
            autodb_article_key="",
            catalog_source="",
            save=Mock(),
        )

        result = service.link_product_with_lookup(
            product=product,
            lookup=lookup,
            normalized_brand="AUTEX",
            normalized_article="820099",
            dry_run=True,
        )

        self.assertTrue(result.linked)
        self.assertEqual(product.autodb_article_key, "300:820099")
        self.assertEqual(result.link_status, "linked")
        product.save.assert_not_called()

    @patch("apps.autodb.services.product_linker.AutoDbProductLinkService._resolve_manual_mapping")
    def test_link_product_uses_confirmed_manual_mapping(self, resolve_manual_mapping_mock):
        lookup_service = Mock()
        lookup_service.lookup.return_value = ArticleLookupResult(
            found=False,
            normalized_brand="NGK",
            normalized_article="SIFR6A11",
            supplier_id=None,
            article_key="",
            article_id=None,
            canonical_article_number="",
            canonical_brand="NGK",
            supplier_source="local",
            article_source="not_found",
            warnings=["article_not_found"],
        )
        resolve_manual_mapping_mock.return_value = SimpleNamespace(
            autodb_supplier_id=15,
            autodb_article_id=777,
            autodb_article_number="SIFR6A-11",
            autodb_article_key="15:SIFR6A-11",
            brand="NGK",
        )
        service = AutoDbProductLinkService(lookup_service=lookup_service)

        product = SimpleNamespace(
            id="p-manual",
            normalized_brand="",
            normalized_article="",
            autodb_supplier_id=None,
            autodb_article_id=None,
            autodb_article_number="",
            autodb_article_key="",
            catalog_source="",
            save=Mock(),
        )

        result = service.link_product(product=product, brand_name="NGK", article="SIFR6A11")

        self.assertTrue(result.linked)
        self.assertEqual(result.link_status, "linked_manual_mapping")
        self.assertIn("manual_mapping_applied", result.warnings)
        self.assertEqual(product.autodb_article_key, "15:SIFR6A-11")

    @patch("apps.autodb.services.product_linker.AutoDbProductLinkService._resolve_manual_mapping", return_value=None)
    def test_link_product_marks_needs_manual_mapping_when_not_found(self, _resolve_manual_mapping_mock):
        lookup_service = Mock()
        lookup_service.lookup.return_value = ArticleLookupResult(
            found=False,
            normalized_brand="NGK",
            normalized_article="SIFR6A11",
            supplier_id=None,
            article_key="",
            article_id=None,
            canonical_article_number="",
            canonical_brand="NGK",
            supplier_source="local",
            article_source="not_found",
            warnings=["article_not_found"],
        )
        service = AutoDbProductLinkService(lookup_service=lookup_service)
        product = SimpleNamespace(
            id="p-missing",
            normalized_brand="",
            normalized_article="",
            autodb_supplier_id=None,
            autodb_article_id=None,
            autodb_article_number="",
            autodb_article_key="",
            catalog_source="",
            save=Mock(),
        )

        result = service.link_product(product=product, brand_name="NGK", article="SIFR6A11")

        self.assertFalse(result.linked)
        self.assertEqual(result.link_status, "needs_manual_mapping")
        self.assertIn("needs_manual_mapping", result.warnings)

    @patch("apps.autodb.services.product_linker.AutoDbArticleManualMapping.objects")
    def test_manual_mapping_requires_confirmed_and_confident(self, objects_mock):
        chain = Mock()
        objects_mock.filter.return_value = chain
        chain.exclude.return_value = chain
        chain.order_by.return_value = chain
        chain.first.return_value = None

        service = AutoDbProductLinkService(lookup_service=Mock())
        service._resolve_manual_mapping(normalized_brand="NGK", normalized_article="SIFR6A11")

        objects_mock.filter.assert_called_once_with(
            normalized_brand="NGK",
            normalized_article="SIFR6A11",
            manual_confirmed=True,
            confidence__gte=service.MIN_MANUAL_MAPPING_CONFIDENCE,
        )

    def test_remote_hit_triggers_related_enrichment(self):
        lookup_service = Mock()
        lookup_service.lookup.return_value = ArticleLookupResult(
            found=True,
            normalized_brand="NGK",
            normalized_article="0127",
            supplier_id=15,
            article_key="15:0127",
            article_id=None,
            canonical_article_number="0127",
            canonical_brand="NGK",
            supplier_source="local",
            article_source="remote",
            remote_article_called=True,
        )
        enrichment_service = Mock()
        enrichment_service.enrich_article.return_value = SimpleNamespace(warnings=[])
        service = AutoDbProductLinkService(
            lookup_service=lookup_service,
            enrichment_service=enrichment_service,
        )
        product = SimpleNamespace(
            id="p-remote",
            normalized_brand="",
            normalized_article="",
            autodb_supplier_id=None,
            autodb_article_id=None,
            autodb_article_number="",
            autodb_article_key="",
            catalog_source="",
            save=Mock(),
        )

        result = service.link_product(product=product, brand_name="NGK", article="0127", dry_run=False, allow_remote=True)

        self.assertTrue(result.linked)
        enrichment_service.enrich_article.assert_called_once()
