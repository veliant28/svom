from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from apps.autodb.services.article_enrichment import ArticleEnrichmentResult
from apps.autodb.services.linked_product_related_enrichment import LinkedProductRelatedLocalState
from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult


class _FakeQuerySet:
    def __init__(self, items):
        self._items = list(items)

    def iterator(self, chunk_size=200):
        return iter(self._items)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return _FakeQuerySet(self._items[item])
        raise TypeError("Only slicing is supported")


class _FakeStateStore:
    def __init__(self):
        self.loaded = None
        self.saved_progress = []
        self.finished = []
        self.running = []

    def load(self, *, state_key: str):
        return self.loaded

    def mark_running(self, **kwargs):
        self.running.append(kwargs)
        return None

    def save_progress(self, **kwargs):
        self.saved_progress.append(kwargs)
        return None

    def finish(self, **kwargs):
        self.finished.append(kwargs)
        return None


class AutoDbEnrichLinkedProductRelatedCommandTests(SimpleTestCase):
    def _ready(self) -> LocalAutoDbReadinessResult:
        return LocalAutoDbReadinessResult(
            ready=True,
            reason="ready",
            error_message="",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=1,
            waited_seconds=0.0,
        )

    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.LinkedProductRelatedStateStore")
    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.AutoDbLinkedProductRelatedEnrichmentService")
    def test_dry_run_local_only_summary(self, service_cls_mock, ready_mock, store_cls_mock):
        ready_mock.return_value = self._ready()
        product = SimpleNamespace(id="p1", autodb_supplier_id=324, autodb_article_number="WL7042")
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet([product])
        service.is_suspicious_for_related_enrichment.return_value = False
        service.inspect_local_state.return_value = LinkedProductRelatedLocalState(
            article_exists=True,
            article_prd_rows=0,
            article_links_rows=0,
            prd_rows=0,
        )
        store_cls_mock.return_value = _FakeStateStore()
        out = StringIO()

        call_command(
            "autodb_enrich_linked_product_related",
            "--only-linked",
            "--limit",
            "10",
            "--dry-run",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("processed_products_this_run: 1", output)
        self.assertIn("total_scope_products: 1", output)
        self.assertIn("remote_disabled_reason: dry_run_requires_allow_remote", output)
        self.assertIn("UTR calls: 0", output)
        service.enrich_related.assert_not_called()

    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.LinkedProductRelatedStateStore")
    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.AutoDbRemoteConfigValidator.ensure_remote_ready")
    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.AutoDbLinkedProductRelatedEnrichmentService")
    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED=True,
    )
    def test_real_run_uses_remote_and_accumulates(self, service_cls_mock, _ensure_ready_mock, ready_mock, store_cls_mock):
        ready_mock.return_value = self._ready()
        product = SimpleNamespace(id="p1", autodb_supplier_id=324, autodb_article_number="WL7042")
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet([product])
        service.is_suspicious_for_related_enrichment.return_value = False
        service.inspect_local_state.side_effect = [
            LinkedProductRelatedLocalState(article_exists=True, article_prd_rows=1, article_links_rows=1, prd_rows=1),
            LinkedProductRelatedLocalState(article_exists=True, article_prd_rows=3, article_links_rows=4, prd_rows=2),
        ]
        service.enrich_related.return_value = ArticleEnrichmentResult(
            article_id=None,
            supplier_id=324,
            article_number="WL7042",
            populated_tables={"article_prd": 2, "article_links": 3, "prd": 1},
            skipped_tables=[],
            warnings=[],
            remote_queries=3,
            remote_hits=6,
        )
        store = _FakeStateStore()
        store_cls_mock.return_value = store
        out = StringIO()

        call_command(
            "autodb_enrich_linked_product_related",
            "--only-linked",
            "--limit",
            "10",
            "--state-key",
            "test_related_1",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("remote_queries: 3", output)
        self.assertIn("remote_hits: 6", output)
        self.assertIn("article_prd_rows_created: 2", output)
        self.assertIn("article_links_rows_created: 3", output)
        self.assertIn("prd_rows_created: 1", output)
        self.assertIn("status: completed", output)
        self.assertGreaterEqual(len(store.saved_progress), 1)
        self.assertGreaterEqual(len(store.finished), 1)

    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.LinkedProductRelatedStateStore")
    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.AutoDbRemoteConfigValidator.ensure_remote_ready")
    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.AutoDbLinkedProductRelatedEnrichmentService")
    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED=True,
    )
    def test_quota_error_aborts_cleanly(self, service_cls_mock, _ensure_ready_mock, ready_mock, store_cls_mock):
        ready_mock.return_value = self._ready()
        product = SimpleNamespace(id="p1", autodb_supplier_id=324, autodb_article_number="WL7042")
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet([product])
        service.is_suspicious_for_related_enrichment.return_value = False
        service.inspect_local_state.return_value = LinkedProductRelatedLocalState(
            article_exists=True,
            article_prd_rows=0,
            article_links_rows=0,
            prd_rows=0,
        )
        service.enrich_related.side_effect = RuntimeError("1226 (42000): User has exceeded the 'max_questions' resource")
        store = _FakeStateStore()
        store_cls_mock.return_value = store
        out = StringIO()

        call_command(
            "autodb_enrich_linked_product_related",
            "--only-linked",
            "--limit",
            "10",
            "--state-key",
            "test_related_2",
            "--stop-on-remote-quota",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("aborted: True", output)
        self.assertIn("abort_reason: remote_quota_exceeded", output)
        self.assertIn("remote_quota_exceeded: True", output)
        self.assertIn("failed: 0", output)
        self.assertTrue(store.finished)

    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.LinkedProductRelatedStateStore")
    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.AutoDbLinkedProductRelatedEnrichmentService")
    def test_skip_local_complete_avoids_remote_calls(self, service_cls_mock, ready_mock, store_cls_mock):
        ready_mock.return_value = self._ready()
        product = SimpleNamespace(id="p1", autodb_supplier_id=324, autodb_article_number="WL7042")
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet([product])
        service.is_suspicious_for_related_enrichment.return_value = False
        service.inspect_local_state.return_value = LinkedProductRelatedLocalState(
            article_exists=True,
            article_prd_rows=5,
            article_links_rows=2,
            prd_rows=3,
        )
        store_cls_mock.return_value = _FakeStateStore()
        out = StringIO()

        call_command(
            "autodb_enrich_linked_product_related",
            "--only-linked",
            "--limit",
            "10",
            "--dry-run",
            "--skip-local-complete",
            "--allow-remote",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("skipped_local_complete: 1", output)
        service.enrich_related.assert_not_called()

    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.LinkedProductRelatedStateStore")
    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_enrich_linked_product_related.AutoDbLinkedProductRelatedEnrichmentService")
    def test_resume_uses_saved_offset(self, service_cls_mock, ready_mock, store_cls_mock):
        ready_mock.return_value = self._ready()
        p1 = SimpleNamespace(id="p1", autodb_supplier_id=324, autodb_article_number="A1")
        p2 = SimpleNamespace(id="p2", autodb_supplier_id=324, autodb_article_number="A2")
        p3 = SimpleNamespace(id="p3", autodb_supplier_id=324, autodb_article_number="A3")
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet([p1, p2, p3])
        service.is_suspicious_for_related_enrichment.return_value = False
        service.inspect_local_state.return_value = LinkedProductRelatedLocalState(
            article_exists=True,
            article_prd_rows=0,
            article_links_rows=0,
            prd_rows=0,
        )
        store = _FakeStateStore()
        store.loaded = SimpleNamespace(last_offset=2)
        store_cls_mock.return_value = store
        out = StringIO()

        call_command(
            "autodb_enrich_linked_product_related",
            "--only-linked",
            "--limit",
            "10",
            "--dry-run",
            "--resume",
            "--state-key",
            "test_related_3",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("processed_products_this_run: 1", output)
        self.assertIn("processed_products_total: 3", output)
