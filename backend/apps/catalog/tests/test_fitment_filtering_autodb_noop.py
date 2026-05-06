from __future__ import annotations

from django.test import TestCase, override_settings

from apps.catalog.models import Brand, Category, Product
from apps.catalog.services.fitment_filtering import FitmentFilteringService
from apps.compatibility.models import ProductFitment


@override_settings(FITMENT_PROVIDER="autodb")
class FitmentFilteringAutodbNoopTests(TestCase):
    def test_autodb_source_product_fitments_do_not_enable_public_fitment_mode(self):
        brand = Brand.objects.create(name="Brand", slug="brand-fitment-noop", is_active=True)
        category = Category.objects.create(name="Category", slug="category-fitment-noop", is_active=True)
        product = Product.objects.create(
            sku="NOOP-FIT-1",
            article="NOOP-FIT-1",
            name="Noop Fitment Product",
            slug="noop-fitment-product",
            brand=brand,
            category=category,
            is_active=True,
        )
        ProductFitment.objects.create(
            product=product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=101,
            linkage_type="PassengerCar",
            autodb_article_key="324:92131E",
            supplier_id=324,
            article_number="92131E",
            note="Auto-DB Pro applicability",
            is_exact=False,
        )

        queryset = Product.objects.filter(id=product.id)
        filtered, _ = FitmentFilteringService().apply(queryset=queryset, params={"fitment": "with_data"})

        self.assertEqual(filtered.count(), 0)
