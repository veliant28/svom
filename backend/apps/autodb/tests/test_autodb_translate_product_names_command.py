from __future__ import annotations

from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.catalog.models import Product


class AutoDbTranslateProductNamesCommandTests(SimpleTestCase):
    @patch("apps.autodb.management.commands.autodb_translate_product_names.Command._process_product")
    @patch("apps.autodb.management.commands.autodb_translate_product_names.Product.objects")
    def test_only_pending_filter_used(self, objects_mock, process_mock):
        qs = Mock()
        qs.filter.return_value = qs
        qs.order_by.return_value = qs
        qs.iterator.return_value = []
        objects_mock.order_by.return_value = qs
        out = StringIO()

        call_command("autodb_translate_product_names", "--only-pending", stdout=out)

        self.assertTrue(qs.filter.called)
        self.assertIn("product translation summary", out.getvalue().lower())
        process_mock.assert_not_called()

    def test_process_product_respects_manual_lock(self):
        from apps.autodb.management.commands.autodb_translate_product_names import Command

        command = Command()
        translator = Mock()
        product = Mock(
            id="p1",
            name_manually_locked=True,
            name_source_text="Амортизатор",
            name_source="autodb_pro",
            name_source_hash="",
            name_translation_status="pending",
            name_uk="",
            name_ru="",
            name_en="",
            save=Mock(),
        )

        status, translation_status = command._process_product(product=product, translator=translator, dry_run=False)

        self.assertEqual(status, "skipped_manual_locked")
        self.assertEqual(translation_status, Product.NAME_TRANSLATION_MANUAL_LOCKED)
        translator.translate_product_name.assert_not_called()
        product.save.assert_not_called()

    def test_process_product_respects_manual_lock_status(self):
        from apps.autodb.management.commands.autodb_translate_product_names import Command

        command = Command()
        translator = Mock()
        product = Mock(
            id="p1-status-lock",
            name_manually_locked=False,
            name_source_text="Амортизатор",
            name_source="autodb_pro",
            name_source_hash="",
            name_translation_status=Product.NAME_TRANSLATION_MANUAL_LOCKED,
            name_uk="",
            name_ru="",
            name_en="",
            save=Mock(),
        )

        status, translation_status = command._process_product(product=product, translator=translator, dry_run=False)

        self.assertEqual(status, "skipped_manual_locked")
        self.assertEqual(translation_status, Product.NAME_TRANSLATION_MANUAL_LOCKED)
        translator.translate_product_name.assert_not_called()
        product.save.assert_not_called()

    def test_process_product_skips_when_hash_unchanged(self):
        from hashlib import sha1

        from apps.autodb.management.commands.autodb_translate_product_names import Command

        command = Command()
        translator = Mock()
        source_text = "Свічка запалювання"
        source_hash = sha1("autodb_pro:Свічка запалювання".encode("utf-8")).hexdigest()  # noqa: S324
        product = Mock(
            id="p2",
            name_manually_locked=False,
            name_source_text=source_text,
            name_source="autodb_pro",
            name_source_hash=source_hash,
            name_translation_status=Product.NAME_TRANSLATION_TRANSLATED,
            name_uk="Свічка запалювання",
            name_ru="Свеча зажигания",
            name_en="Spark plug",
            save=Mock(),
        )

        status, translation_status = command._process_product(product=product, translator=translator, dry_run=False)

        self.assertEqual(status, "skipped_hash_unchanged")
        self.assertEqual(translation_status, Product.NAME_TRANSLATION_TRANSLATED)
        translator.translate_product_name.assert_not_called()
        product.save.assert_not_called()
