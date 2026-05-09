from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.product_attribute_enrichment import ProductAttributeEnrichmentResult


class _FakeQuerySet:
    def __init__(self, items):
        self._items = list(items)

    def iterator(self, chunk_size=200):
        return iter(self._items)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return _FakeQuerySet(self._items[item])
        raise TypeError("Only slicing is supported in fake queryset")


class AutoDbUpdateProductAttributesCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_update_product_attributes.wait_for_local_autodb_ready",
        return_value=LocalAutoDbReadinessResult(
            ready=True,
            reason="ready",
            error_message="",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=1,
            waited_seconds=0.0,
        ),
    )
    @patch("apps.autodb.management.commands.autodb_update_product_attributes.AutoDbProductAttributeEnrichmentService")
    def test_dry_run_outputs_summary(self, service_cls_mock, _ready_mock):
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet([SimpleNamespace(id="p1"), SimpleNamespace(id="p2")])
        service.enrich_product.side_effect = [
            ProductAttributeEnrichmentResult(
                product_id="p1",
                status="updated",
                attributes_found=2,
                attributes_created=1,
                attributes_reused=1,
                values_created=2,
                product_attributes_created=2,
                product_attributes_updated=0,
                skipped_manual_locked=0,
                translation_pending=1,
            ),
            ProductAttributeEnrichmentResult(
                product_id="p2",
                status="skipped_no_article_attributes",
                attributes_found=0,
                attributes_created=0,
                attributes_reused=0,
                values_created=0,
                product_attributes_created=0,
                product_attributes_updated=0,
                skipped_manual_locked=0,
                translation_pending=0,
            ),
        ]

        out = StringIO()
        call_command("autodb_update_product_attributes", "--dry-run", stdout=out)
        service.build_queryset.assert_called_once_with(
            only_linked=False,
            only_trusted=False,
            only_missing=False,
            product_id="",
        )

        output = out.getvalue()
        self.assertIn("Auto_DB_Pro product attribute update summary", output)
        self.assertIn("- processed: 2", output)
        self.assertIn("- products_with_attributes: 1", output)
        self.assertIn("- attributes_created: 1", output)
        self.assertIn("- product_attributes_created: 2", output)
        self.assertIn("UTR calls: 0", output)

    @patch(
        "apps.autodb.management.commands.autodb_update_product_attributes.wait_for_local_autodb_ready",
        return_value=LocalAutoDbReadinessResult(
            ready=True,
            reason="ready",
            error_message="",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=1,
            waited_seconds=0.0,
        ),
    )
    @patch("apps.autodb.management.commands.autodb_update_product_attributes.AutoDbProductAttributeEnrichmentService")
    def test_failed_counter_increments(self, service_cls_mock, _ready_mock):
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet([SimpleNamespace(id="p1")])
        service.enrich_product.side_effect = RuntimeError("boom")

        out = StringIO()
        call_command("autodb_update_product_attributes", "--dry-run", stdout=out)
        service.build_queryset.assert_called_once_with(
            only_linked=False,
            only_trusted=False,
            only_missing=False,
            product_id="",
        )

        output = out.getvalue()
        self.assertIn("status=failed", output)
        self.assertIn("- failed: 1", output)

    @patch(
        "apps.autodb.management.commands.autodb_update_product_attributes.wait_for_local_autodb_ready",
        return_value=LocalAutoDbReadinessResult(
            ready=True,
            reason="ready",
            error_message="",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=1,
            waited_seconds=0.0,
        ),
    )
    @patch("apps.autodb.management.commands.autodb_update_product_attributes.AutoDbProductAttributeEnrichmentService")
    def test_only_trusted_flag_is_forwarded(self, service_cls_mock, _ready_mock):
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet([])

        out = StringIO()
        call_command("autodb_update_product_attributes", "--dry-run", "--only-trusted", "--only-linked", stdout=out)

        service.build_queryset.assert_called_once_with(
            only_linked=True,
            only_trusted=True,
            only_missing=False,
            product_id="",
        )
