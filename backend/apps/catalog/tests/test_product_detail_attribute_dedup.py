from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.catalog.api.serializers.product_detail_serializer import ProductDetailSerializer
from apps.catalog.models import Attribute, AttributeValue, Brand, Product, ProductAttribute


class ProductDetailAttributeDedupTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="ERT", slug="ert")
        self.product = Product.objects.create(
            sku="dedup-1",
            article="500414",
            name="Test",
            name_uk="Test",
            name_ru="Test",
            name_en="Test",
            slug="dedup-product",
            brand=self.brand,
            is_active=True,
        )

        attr_uk = Attribute.objects.create(name="висота", slug="vysota-uk", source=Attribute.SOURCE_AUTODB_PRO)
        val_uk = AttributeValue.objects.create(attribute=attr_uk, value="82.15 мм", source=AttributeValue.SOURCE_AUTODB_PRO)
        ProductAttribute.objects.create(
            product=self.product,
            attribute=attr_uk,
            attribute_value=val_uk,
            source=ProductAttribute.SOURCE_AUTODB_PRO,
        )

        attr_ru = Attribute.objects.create(name="высота", slug="vysota-ru", source=Attribute.SOURCE_AUTODB_PRO)
        val_ru = AttributeValue.objects.create(attribute=attr_ru, value="82.15 мм", source=AttributeValue.SOURCE_AUTODB_PRO)
        ProductAttribute.objects.create(
            product=self.product,
            attribute=attr_ru,
            attribute_value=val_ru,
            source=ProductAttribute.SOURCE_AUTODB_PRO,
        )

    def test_ru_locale_deduplicates_same_value_prefers_ru_name(self):
        request = Request(APIRequestFactory().get("/api/catalog/products/dedup-product/?locale=ru"))
        serializer = ProductDetailSerializer(instance=self.product, context={"request": request})

        attrs = serializer.get_attributes(self.product)

        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0]["attribute_name"], "высота")
        self.assertEqual(attrs[0]["value"], "82.15 мм")
