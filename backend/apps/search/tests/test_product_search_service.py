from unittest.mock import patch

from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.search.services.product_search import ProductSearchService


class ProductSearchServiceTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="K2", slug="k2", is_active=True)
        self.category = Category.objects.create(
            name="Ароматизаторы",
            slug="aromatizatory",
            source=Category.SOURCE_MANUAL,
            is_active=True,
            show_in_header=False,
        )
        self.product = Product.objects.create(
            sku="GPL-000000004396582",
            article="V203D",
            name="Освежитель K2",
            slug="osvezhitel-k2",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

    @patch("apps.search.services.product_search.is_elasticsearch_enabled", return_value=True)
    @patch.object(ProductSearchService, "_search_ids_elasticsearch")
    def test_falls_back_to_db_when_es_ids_do_not_match_queryset(self, search_ids_mock, _es_enabled_mock):
        search_ids_mock.return_value = ["00000000-0000-0000-0000-000000000000"]

        queryset = Product.objects.filter(is_active=True)
        result = ProductSearchService().apply(queryset, "000000004396582")

        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().id, self.product.id)
