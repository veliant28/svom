from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.product_image_enrichment import AutoDbImageSyncResult
from apps.supplier_imports.services.gpl_images import GplImageSyncResult


class _FakeQuerySet:
    def __init__(self, items):
        self._items = list(items)

    def iterator(self, chunk_size=200):
        return iter(self._items)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return _FakeQuerySet(self._items[item])
        raise TypeError("Only slicing is supported")

    def filter(self, **kwargs):
        return self

    def exclude(self, **kwargs):
        return self

    def select_related(self, *args, **kwargs):
        return self

    def prefetch_related(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def distinct(self):
        return self


class AutoDbUpdateProductImagesCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_update_product_images.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_update_product_images.Product.objects")
    @patch("apps.autodb.management.commands.autodb_update_product_images.GplProductImageService")
    @patch("apps.autodb.management.commands.autodb_update_product_images.AutoDbProductImageEnrichmentService")
    def test_outputs_summary(self, autodb_cls_mock, gpl_cls_mock, product_objects_mock, _ready_mock):
        product_objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = _FakeQuerySet(
            [SimpleNamespace(id="p1"), SimpleNamespace(id="p2")]
        )
        gpl_service = gpl_cls_mock.return_value
        autodb_service = autodb_cls_mock.return_value
        gpl_service.sync_product_images.side_effect = [
            GplImageSyncResult(product_id="p1", source_code="gpl", has_candidates=True, created=1, reused=0, stale_marked=0, skipped_manual_primary=False),
            GplImageSyncResult(product_id="p2", source_code="", has_candidates=False, created=0, reused=0, stale_marked=0, skipped_manual_primary=False),
        ]
        autodb_service.sync_product_images.side_effect = [
            AutoDbImageSyncResult(product_id="p1", has_candidates=True, created=1, reused=0, stale_marked=0, skipped_manual_primary=False, skipped_no_autodb_link=False),
            AutoDbImageSyncResult(product_id="p2", has_candidates=False, created=0, reused=0, stale_marked=0, skipped_manual_primary=False, skipped_no_autodb_link=True),
        ]

        out = StringIO()
        call_command("autodb_update_product_images", "--dry-run", stdout=out)

        output = out.getvalue()
        self.assertIn("Auto_DB_Pro product image update summary", output)
        self.assertIn("- processed: 2", output)
        self.assertIn("- gpl_images_created: 1", output)
        self.assertIn("- autodb_images_created: 1", output)
        self.assertIn("- skipped_no_autodb_link: 1", output)
        self.assertIn("UTR calls: 0", output)

    @patch(
        "apps.autodb.management.commands.autodb_update_product_images.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_update_product_images.Product.objects")
    @patch("apps.autodb.management.commands.autodb_update_product_images.GplProductImageService")
    @patch("apps.autodb.management.commands.autodb_update_product_images.AutoDbProductImageEnrichmentService")
    def test_only_trusted_flag_keeps_command_readable(self, autodb_cls_mock, gpl_cls_mock, product_objects_mock, _ready_mock):
        product_objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = _FakeQuerySet(
            [SimpleNamespace(id="p1")]
        )
        gpl_cls_mock.return_value.sync_product_images.return_value = GplImageSyncResult(
            product_id="p1", source_code="gpl", has_candidates=False, created=0, reused=0, stale_marked=0, skipped_manual_primary=False
        )
        autodb_cls_mock.return_value.sync_product_images.return_value = AutoDbImageSyncResult(
            product_id="p1", has_candidates=False, created=0, reused=0, stale_marked=0, skipped_manual_primary=False, skipped_no_autodb_link=False
        )

        out = StringIO()
        call_command("autodb_update_product_images", "--dry-run", "--only-linked", "--only-trusted", stdout=out)

        self.assertIn("only_trusted=True", out.getvalue())

    @patch(
        "apps.autodb.management.commands.autodb_update_product_images.wait_for_local_autodb_ready",
        return_value=LocalAutoDbReadinessResult(
            ready=False,
            reason="db_starting_or_recovering",
            error_message="not yet accepting connections",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=3,
            waited_seconds=4.0,
        ),
    )
    @patch("apps.autodb.management.commands.autodb_update_product_images.Product.objects")
    def test_aborts_summary_when_local_db_not_ready(self, product_objects_mock, ready_mock):
        product_objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = _FakeQuerySet(
            [SimpleNamespace(id="p1")]
        )
        out = StringIO()

        call_command("autodb_update_product_images", "--dry-run", "--wait-for-autodb", "300", stdout=out)

        output = out.getvalue()
        ready_mock.assert_called_once_with(timeout_seconds=300, interval_seconds=2.0)
        self.assertIn("- processed: 0", output)
        self.assertIn("- failed: 0", output)
        self.assertIn("- aborted: True", output)
        self.assertIn("- abort_reason: local_autodb_not_ready", output)
