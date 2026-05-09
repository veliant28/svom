from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.product_fitment_enrichment import ProductFitmentEnrichmentResult


class _FakeQuerySet:
    def __init__(self, items):
        self._items = list(items)

    def iterator(self, chunk_size=200):
        return iter(self._items)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return _FakeQuerySet(self._items[item])
        raise TypeError("Only slicing is supported")


class AutoDbUpdateProductFitmentsCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_update_product_fitments.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_update_product_fitments.AutoDbProductFitmentEnrichmentService")
    def test_outputs_summary(self, service_cls_mock, _ready_mock):
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet([SimpleNamespace(id="p1"), SimpleNamespace(id="p2")])
        service.enrich_product.side_effect = [
            ProductFitmentEnrichmentResult(
                product_id="p1",
                status="updated",
                has_fitments=True,
                fitments_created=2,
                fitments_updated=1,
                stale_marked=1,
                skipped_no_autodb_link=False,
                skipped_no_article_li=False,
                skipped_non_passenger_car=False,
                skipped_missing_passanger_car=False,
                skipped_manual_locked=False,
            ),
            ProductFitmentEnrichmentResult(
                product_id="p2",
                status="skipped_no_article_li",
                has_fitments=False,
                fitments_created=0,
                fitments_updated=0,
                stale_marked=0,
                skipped_no_autodb_link=False,
                skipped_no_article_li=True,
                skipped_non_passenger_car=False,
                skipped_missing_passanger_car=False,
                skipped_manual_locked=False,
            ),
        ]

        out = StringIO()
        call_command("autodb_update_product_fitments", "--dry-run", stdout=out)
        service.build_queryset.assert_called_once_with(product_id="", only_linked=False, only_trusted=False)

        output = out.getvalue()
        self.assertIn("Auto_DB_Pro product fitment update summary", output)
        self.assertIn("- processed: 2", output)
        self.assertIn("- products_with_fitments: 1", output)
        self.assertIn("- fitments_created: 2", output)
        self.assertIn("- fitments_updated: 1", output)
        self.assertIn("- stale_marked: 1", output)
        self.assertIn("- skipped_no_article_li: 1", output)
        self.assertIn("UTR calls: 0", output)

    @patch(
        "apps.autodb.management.commands.autodb_update_product_fitments.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_update_product_fitments.AutoDbProductFitmentEnrichmentService")
    def test_aborts_when_local_db_not_ready(self, service_cls_mock, ready_mock):
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet([SimpleNamespace(id="p1")])

        out = StringIO()
        call_command("autodb_update_product_fitments", "--dry-run", "--wait-for-autodb", "300", stdout=out)
        service.build_queryset.assert_called_once_with(product_id="", only_linked=False, only_trusted=False)

        output = out.getvalue()
        ready_mock.assert_called_once_with(timeout_seconds=300, interval_seconds=2.0)
        self.assertIn("- processed: 0", output)
        self.assertIn("- failed: 0", output)
        self.assertIn("- aborted: True", output)
        self.assertIn("- abort_reason: local_autodb_not_ready", output)

    @patch(
        "apps.autodb.management.commands.autodb_update_product_fitments.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_update_product_fitments.AutoDbProductFitmentEnrichmentService")
    def test_only_trusted_flag_is_forwarded(self, service_cls_mock, _ready_mock):
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet([])

        out = StringIO()
        call_command("autodb_update_product_fitments", "--dry-run", "--only-linked", "--only-trusted", stdout=out)

        service.build_queryset.assert_called_once_with(product_id="", only_linked=True, only_trusted=True)
