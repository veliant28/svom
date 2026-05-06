from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.catalog.services.product_management import (
    get_admin_display_name,
    get_product_display_name,
    get_product_display_name_with_meta,
    is_code_like_product_name,
)


class ProductNameDisplayHelperTests(SimpleTestCase):
    def test_admin_display_includes_brand_and_article(self):
        product = SimpleNamespace(
            name_uk="Свічка запалювання",
            name="Свічка запалювання",
            article="SIFR6A11",
            autodb_article_number="",
            brand=SimpleNamespace(name="NGK"),
        )

        label = get_admin_display_name(product)

        self.assertEqual(label, "Свічка запалювання - NGK SIFR6A11")

    def test_product_name_itself_is_not_modified(self):
        product = SimpleNamespace(
            name_uk="Свічка запалювання",
            name="Свічка запалювання",
            article="SIFR6A11",
            autodb_article_number="SIFR6A11",
            brand=SimpleNamespace(name="NGK"),
        )

        _ = get_admin_display_name(product)

        self.assertEqual(product.name_uk, "Свічка запалювання")
        self.assertNotIn("SIFR6A11", product.name_uk)

    def test_public_display_uses_selected_language(self):
        product = SimpleNamespace(
            name="Spark Plug",
            name_uk="Свічка запалювання",
            name_ru="Свеча зажигания",
            name_en="Spark Plug",
            name_source_text="",
            article="SIFR6A11",
            autodb_article_number="",
            sku="SIFR6A11",
            brand=SimpleNamespace(name="NGK"),
            category=SimpleNamespace(get_localized_name=lambda _locale: "Товар"),
        )

        self.assertEqual(get_product_display_name(product, "ru"), "Свеча зажигания")
        self.assertEqual(get_product_display_name(product, "en"), "Spark Plug")
        self.assertEqual(get_product_display_name(product, "uk"), "Свічка запалювання")

    def test_code_like_name_falls_back_to_category_brand_article(self):
        product = SimpleNamespace(
            name="CS0100",
            name_uk="",
            name_ru="",
            name_en="",
            name_source_text="",
            article="CS0100",
            autodb_article_number="",
            sku="CS0100",
            brand=SimpleNamespace(name="NGK"),
            category=SimpleNamespace(get_localized_name=lambda _locale: "Товар"),
        )

        label = get_product_display_name(product, "uk")

        self.assertEqual(label, "Товар NGK CS0100")
        self.assertTrue(is_code_like_product_name("CS0100"))

    def test_leading_numeric_and_trailing_code_are_cleaned(self):
        product = SimpleNamespace(
            name="0005 Свічка запалювання TR5A-10",
            name_uk="0005 Свічка запалювання TR5A-10",
            name_ru="",
            name_en="",
            name_source_text="",
            article="TR5A-10",
            autodb_article_number="",
            sku="TR5A-10",
            brand=SimpleNamespace(name="NGK"),
            category=SimpleNamespace(get_localized_name=lambda _locale: "Товар"),
        )

        self.assertEqual(get_product_display_name(product, "uk"), "Свічка запалювання")

    def test_admin_meta_fallback_uses_unknown_label_with_brand_article(self):
        product = SimpleNamespace(
            name="CS0100",
            name_uk="CS0100",
            name_ru="CS0100",
            name_en="CS0100",
            name_source_text="",
            article="CS0100",
            autodb_article_number="",
            sku="CS0100",
            brand=SimpleNamespace(name="CS SYSTEM"),
            category=SimpleNamespace(get_localized_name=lambda _locale: "Автоемалі"),
        )

        label, source = get_product_display_name_with_meta(product, "uk", unknown_label="Товар без названия")

        self.assertEqual(label, "Товар без названия CS SYSTEM CS0100")
        self.assertEqual(source, "fallback")
