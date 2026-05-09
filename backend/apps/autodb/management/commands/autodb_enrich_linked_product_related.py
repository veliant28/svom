from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.autodb.models import AutoDbSyncState
from apps.autodb.services import (
    AutoDbLinkedProductRelatedEnrichmentService,
    AutoDbRemoteConfigError,
    AutoDbRemoteConfigValidator,
    LinkedProductRelatedStateStore,
    estimate_remote_queries_for_tables,
    extract_related_tables,
    is_related_local_complete,
    is_remote_quota_error,
)
from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready


@dataclass
class LinkedRelatedEnrichmentSummary:
    processed_products_this_run: int = 0
    processed_products_total: int = 0
    total_scope_products: int = 0
    unique_article_keys: int = 0
    skipped_local_complete: int = 0
    remote_queries: int = 0
    remote_hits: int = 0
    remote_query_budget: int = 0
    remote_quota_exceeded: bool = False
    remote_quota_remaining_estimate: int = -1
    article_prd_rows_created: int = 0
    article_prd_rows_reused: int = 0
    article_links_rows_created: int = 0
    article_links_rows_reused: int = 0
    prd_rows_created: int = 0
    prd_rows_reused: int = 0
    skipped_no_autodb_link: int = 0
    skipped_suspicious_link: int = 0
    failed: int = 0
    aborted: bool = False
    abort_reason: str = ""
    last_product_id: str = ""
    last_offset: int = 0
    status: str = "completed"
    state_saved: bool = False
    state_key: str = ""
    db_error: str = ""


class Command(BaseCommand):
    help = "Targeted related-table enrichment (article_prd/article_links/prd) for linked Products."

    DEFAULT_TABLES = ("article_prd", "article_links", "prd")
    SAFE_TABLES = {
        "articles",
        "article_numbers",
        "article_attributes",
        "article_images",
        "article_inf",
        "article_li",
        "article_links",
        "article_prd",
        "article_oe",
        "article_cross",
        "article_ean",
        "article_nn",
        "article_m",
        "article_acc",
        "article_parts",
        "prd",
    }

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Limit products count")
        parser.add_argument("--dry-run", action="store_true", help="Plan enrichment without persisting clone rows")
        parser.add_argument("--product-id", type=str, default="", help="One Product UUID")
        parser.add_argument("--only-linked", action="store_true", help="Process only products linked to Auto_DB_Pro")
        parser.add_argument("--only-trusted", action="store_true", help="Process only products with trusted Auto_DB link quality")
        parser.add_argument(
            "--tables",
            type=str,
            default="article_prd,article_links,prd",
            help="Comma-separated related tables (default: article_prd,article_links,prd)",
        )
        parser.add_argument("--allow-remote", action="store_true", help="Force remote Auto_DB_Pro usage")
        parser.add_argument("--no-remote", action="store_true", help="Disable remote Auto_DB_Pro usage")
        parser.add_argument(
            "--wait-for-autodb",
            type=int,
            default=0,
            help="Wait up to N seconds for local Auto_DB_Pro DB readiness before processing.",
        )
        parser.add_argument("--batch-size", type=int, default=50, help="Product batch size for iteration and state commits.")
        parser.add_argument("--remote-query-budget", type=int, default=0, help="Max remote queries per run (0 = unlimited).")
        parser.add_argument(
            "--stop-on-remote-quota",
            action="store_true",
            help="Gracefully stop and save state when remote quota (MySQL 1226) is reached.",
        )
        parser.add_argument("--resume", action="store_true", help="Resume from saved state key.")
        parser.add_argument("--state-key", type=str, default="", help="State key for resumable runs.")
        parser.add_argument(
            "--skip-local-complete",
            action="store_true",
            help="Skip keys where requested related rows already exist locally.",
        )
        parser.add_argument(
            "--max-products-per-run",
            type=int,
            default=0,
            help="Stop after processing N products in current run (0 = unlimited).",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        product_id = str(options.get("product_id") or "").strip()
        only_linked = bool(options.get("only_linked"))
        only_trusted = bool(options.get("only_trusted"))
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        limit = max(int(options.get("limit") or 0), 0)
        batch_size = max(int(options.get("batch_size") or 50), 1)
        max_products_per_run = max(int(options.get("max_products_per_run") or 0), 0)
        remote_query_budget = max(int(options.get("remote_query_budget") or 0), 0)
        stop_on_remote_quota = bool(options.get("stop_on_remote_quota"))
        resume = bool(options.get("resume"))
        state_key = str(options.get("state_key") or "").strip() or "linked_related_default"
        skip_local_complete = bool(options.get("skip_local_complete"))
        allow_remote_flag = bool(options.get("allow_remote"))
        no_remote_flag = bool(options.get("no_remote"))
        table_option = str(options.get("tables") or "").strip()

        if allow_remote_flag and no_remote_flag:
            raise CommandError("Use either --allow-remote or --no-remote, not both.")
        if resume and not state_key:
            raise CommandError("--resume requires --state-key.")

        requested_tables = extract_related_tables(item.strip() for item in table_option.split(","))
        tables = requested_tables or list(self.DEFAULT_TABLES)
        invalid_tables = [table for table in tables if table not in self.SAFE_TABLES]
        if invalid_tables:
            raise CommandError(f"Unsupported table(s): {', '.join(sorted(invalid_tables))}")

        summary = LinkedRelatedEnrichmentSummary(
            remote_query_budget=remote_query_budget,
            state_key=state_key,
        )

        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            summary.aborted = True
            summary.abort_reason = "local_autodb_not_ready"
            summary.status = "aborted"
            summary.db_error = readiness.error_message
            self.stdout.write(
                "Auto_DB_Pro local DB is not ready/recovering. Retry later. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} "
                f"reason={readiness.reason} attempts={readiness.attempts} waited_seconds={readiness.waited_seconds}"
            )
            self._print_summary(summary)
            return

        remote_enabled = bool(getattr(settings, "AUTODB_PRO_REMOTE_ENABLED", False))
        remote_lookup_enabled = bool(getattr(settings, "AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED", False))
        requested_remote = False
        remote_disabled_reason = ""
        if no_remote_flag:
            remote_disabled_reason = "flag_no_remote"
        elif dry_run:
            requested_remote = allow_remote_flag
            if not requested_remote:
                remote_disabled_reason = "dry_run_requires_allow_remote"
        else:
            requested_remote = allow_remote_flag or remote_lookup_enabled
            if not requested_remote:
                remote_disabled_reason = "setting_remote_lookup_disabled"

        allow_remote = remote_enabled and requested_remote
        if requested_remote and not remote_enabled:
            remote_disabled_reason = "global_remote_disabled"
        if allow_remote:
            try:
                AutoDbRemoteConfigValidator.ensure_remote_ready(allow_remote=True)
            except AutoDbRemoteConfigError as exc:
                allow_remote = False
                remote_disabled_reason = f"remote_config_error:{exc}"

        service = AutoDbLinkedProductRelatedEnrichmentService()
        state_store = LinkedProductRelatedStateStore()
        state_snapshot = None
        resume_offset = 0
        if resume:
            state_snapshot = state_store.load(state_key=state_key)
            if state_snapshot is not None:
                resume_offset = max(int(state_snapshot.last_offset or 0), 0)

        qs = service.build_queryset(
            only_linked=only_linked,
            only_trusted=only_trusted,
            product_id=product_id,
        )
        if limit > 0:
            qs = qs[:limit]

        products = list(qs.iterator(chunk_size=max(batch_size, 50)))
        summary.total_scope_products = len(products)
        scoped_products = products
        if resume_offset > 0:
            scoped_products = products[resume_offset:]
        summary.processed_products_total = resume_offset

        self.stdout.write(
            "Auto_DB_Pro linked product related enrichment started "
            f"dry_run={dry_run} only_linked={only_linked} only_trusted={only_trusted} "
            f"tables={','.join(tables)} allow_remote={allow_remote} "
            f"wait_for_autodb={wait_for_autodb} batch_size={batch_size} "
            f"remote_query_budget={remote_query_budget or 'unlimited'} stop_on_remote_quota={stop_on_remote_quota} "
            f"resume={resume} state_key={state_key} skip_local_complete={skip_local_complete} "
            f"max_products_per_run={max_products_per_run or 'unlimited'}"
        )

        if not dry_run:
            metadata = {
                "state_key": state_key,
                "tables": tables,
                "limit": limit,
                "only_linked": only_linked,
                "only_trusted": only_trusted,
                "product_id": product_id or "",
                "remote_query_budget": remote_query_budget,
                "skip_local_complete": skip_local_complete,
            }
            state_store.mark_running(
                state_key=state_key,
                total_rows=summary.total_scope_products,
                metadata=metadata,
                resume=resume,
            )
            summary.state_saved = True

        unique_keys: dict[str, tuple[int, str, str]] = {}
        seen_article_keys: set[str] = set()
        for scoped_index, product in enumerate(scoped_products, start=1):
            summary.processed_products_this_run += 1
            summary.processed_products_total += 1
            summary.last_product_id = str(getattr(product, "id", "") or "")
            summary.last_offset = resume_offset + scoped_index

            supplier_id = self._safe_int(getattr(product, "autodb_supplier_id", None))
            article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
            if supplier_id is None or not article_number:
                summary.skipped_no_autodb_link += 1
                self._save_progress_state(
                    dry_run=dry_run,
                    state_store=state_store,
                    summary=summary,
                )
                if self._should_stop_by_run_cap(max_products_per_run=max_products_per_run, summary=summary):
                    break
                continue

            if service.is_suspicious_for_related_enrichment(product=product):
                summary.skipped_suspicious_link += 1
                self._save_progress_state(
                    dry_run=dry_run,
                    state_store=state_store,
                    summary=summary,
                )
                if self._should_stop_by_run_cap(max_products_per_run=max_products_per_run, summary=summary):
                    break
                continue

            key = f"{supplier_id}:{article_number}"
            unique_keys[key] = (supplier_id, article_number, summary.last_product_id)
            if key in seen_article_keys:
                summary.skipped_local_complete += 1
                self._save_progress_state(
                    dry_run=dry_run,
                    state_store=state_store,
                    summary=summary,
                )
                if self._should_stop_by_run_cap(max_products_per_run=max_products_per_run, summary=summary):
                    break
                continue
            seen_article_keys.add(key)

            before = service.inspect_local_state(supplier_id=supplier_id, article_number=article_number)
            if skip_local_complete and is_related_local_complete(state=before, tables=tables):
                summary.skipped_local_complete += 1
                self._save_progress_state(
                    dry_run=dry_run,
                    state_store=state_store,
                    summary=summary,
                )
                if self._should_stop_by_run_cap(max_products_per_run=max_products_per_run, summary=summary):
                    break
                continue

            if not allow_remote:
                self._save_progress_state(
                    dry_run=dry_run,
                    state_store=state_store,
                    summary=summary,
                )
                if self._should_stop_by_run_cap(max_products_per_run=max_products_per_run, summary=summary):
                    break
                continue

            estimated_queries = estimate_remote_queries_for_tables(tables)
            if remote_query_budget > 0 and (summary.remote_queries + estimated_queries) > remote_query_budget:
                summary.aborted = True
                summary.abort_reason = "remote_query_budget_reached"
                summary.status = "paused"
                self._save_progress_state(
                    dry_run=dry_run,
                    state_store=state_store,
                    summary=summary,
                )
                break

            try:
                result = service.enrich_related(
                    supplier_id=supplier_id,
                    article_number=article_number,
                    tables=tables,
                    dry_run=dry_run,
                    allow_remote=allow_remote,
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                if stop_on_remote_quota and is_remote_quota_error(message):
                    summary.aborted = True
                    summary.abort_reason = "remote_quota_exceeded"
                    summary.remote_quota_exceeded = True
                    summary.status = "aborted"
                    summary.db_error = message
                    self._save_progress_state(
                        dry_run=dry_run,
                        state_store=state_store,
                        summary=summary,
                    )
                    break
                summary.failed += 1
                self.stdout.write(f"- article_key={key} status=failed error={exc}")
                self._save_progress_state(
                    dry_run=dry_run,
                    state_store=state_store,
                    summary=summary,
                )
                if self._should_stop_by_run_cap(max_products_per_run=max_products_per_run, summary=summary):
                    break
                continue

            if result is not None:
                summary.remote_queries += int(result.remote_queries)
                summary.remote_hits += int(result.remote_hits)

                if dry_run:
                    self._accumulate_dry_run_table_deltas(summary=summary, before=before, populated=result.populated_tables)
                else:
                    after = service.inspect_local_state(supplier_id=supplier_id, article_number=article_number)
                    self._accumulate_real_table_deltas(
                        summary=summary,
                        before=before,
                        after=after,
                        populated=result.populated_tables,
                    )

            self._save_progress_state(
                dry_run=dry_run,
                state_store=state_store,
                summary=summary,
            )
            if self._should_stop_by_run_cap(max_products_per_run=max_products_per_run, summary=summary):
                break

        summary.unique_article_keys = len(unique_keys)
        if remote_query_budget > 0:
            summary.remote_quota_remaining_estimate = max(remote_query_budget - summary.remote_queries, 0)

        if not dry_run:
            if summary.aborted:
                state_store.finish(
                    state_key=state_key,
                    status=AutoDbSyncState.Status.PAUSED,
                    error=summary.db_error or summary.abort_reason,
                    metadata_patch={
                        "abort_reason": summary.abort_reason or "-",
                        "remote_queries_used": summary.remote_queries,
                    },
                )
                summary.state_saved = True
            elif summary.status == "paused":
                state_store.finish(
                    state_key=state_key,
                    status=AutoDbSyncState.Status.PAUSED,
                    error=summary.abort_reason or "",
                    metadata_patch={
                        "abort_reason": summary.abort_reason or "-",
                        "remote_queries_used": summary.remote_queries,
                    },
                )
                summary.state_saved = True
            else:
                state_store.finish(
                    state_key=state_key,
                    status=AutoDbSyncState.Status.COMPLETED,
                    error="",
                    metadata_patch={
                        "abort_reason": "-",
                        "remote_queries_used": summary.remote_queries,
                    },
                )
                summary.status = "completed"
                summary.state_saved = True
        elif not summary.aborted and summary.status != "paused":
            summary.status = "completed"

        if not summary.aborted and summary.status != "paused":
            summary.abort_reason = summary.abort_reason or "-"
        self._print_summary(summary=summary, remote_disabled_reason=remote_disabled_reason)

    def _save_progress_state(
        self,
        *,
        dry_run: bool,
        state_store: LinkedProductRelatedStateStore,
        summary: LinkedRelatedEnrichmentSummary,
    ) -> None:
        if dry_run:
            return
        state_store.save_progress(
            state_key=summary.state_key,
            processed_rows=summary.processed_products_total,
            failed_rows=summary.failed,
            last_offset=summary.last_offset,
            last_cursor=summary.last_product_id,
            metadata_patch={"remote_queries_used": summary.remote_queries},
        )
        summary.state_saved = True

    def _should_stop_by_run_cap(self, *, max_products_per_run: int, summary: LinkedRelatedEnrichmentSummary) -> bool:
        if max_products_per_run <= 0:
            return False
        if summary.processed_products_this_run < max_products_per_run:
            return False
        summary.status = "paused"
        if not summary.abort_reason:
            summary.abort_reason = "max_products_per_run_reached"
        return True

    def _print_summary(self, *, summary: LinkedRelatedEnrichmentSummary, remote_disabled_reason: str) -> None:
        self.stdout.write("Auto_DB_Pro linked product related enrichment summary:")
        self.stdout.write(f"- processed_products_this_run: {summary.processed_products_this_run}")
        self.stdout.write(f"- processed_products_total: {summary.processed_products_total}")
        self.stdout.write(f"- total_scope_products: {summary.total_scope_products}")
        self.stdout.write(f"- unique_article_keys: {summary.unique_article_keys}")
        self.stdout.write(f"- skipped_local_complete: {summary.skipped_local_complete}")
        self.stdout.write(f"- remote_queries: {summary.remote_queries}")
        self.stdout.write(f"- remote_query_budget: {summary.remote_query_budget or '-'}")
        self.stdout.write(
            f"- remote_quota_remaining_estimate: "
            f"{summary.remote_quota_remaining_estimate if summary.remote_quota_remaining_estimate >= 0 else '-'}"
        )
        self.stdout.write(f"- remote_quota_exceeded: {summary.remote_quota_exceeded}")
        self.stdout.write(f"- remote_hits: {summary.remote_hits}")
        self.stdout.write(f"- article_prd_rows_created: {summary.article_prd_rows_created}")
        self.stdout.write(f"- article_prd_rows_reused: {summary.article_prd_rows_reused}")
        self.stdout.write(f"- article_links_rows_created: {summary.article_links_rows_created}")
        self.stdout.write(f"- article_links_rows_reused: {summary.article_links_rows_reused}")
        self.stdout.write(f"- prd_rows_created: {summary.prd_rows_created}")
        self.stdout.write(f"- prd_rows_reused: {summary.prd_rows_reused}")
        self.stdout.write(f"- skipped_no_autodb_link: {summary.skipped_no_autodb_link}")
        self.stdout.write(f"- skipped_suspicious_link: {summary.skipped_suspicious_link}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write(f"- aborted: {summary.aborted}")
        self.stdout.write(f"- abort_reason: {summary.abort_reason or '-'}")
        self.stdout.write(f"- status: {summary.status}")
        self.stdout.write(f"- state_saved: {summary.state_saved}")
        self.stdout.write(f"- state_key: {summary.state_key or '-'}")
        self.stdout.write(f"- last_product_id: {summary.last_product_id or '-'}")
        self.stdout.write(f"- last_offset: {summary.last_offset}")
        self.stdout.write(f"- db_error: {summary.db_error or '-'}")
        self.stdout.write(f"- remote_disabled_reason: {remote_disabled_reason or '-'}")
        self.stdout.write("- UTR calls: 0")
        self.stdout.write("- price/stock changed: 0")
        self.stdout.write("- product/name/category changed: 0")
        self.stdout.write("- compatibility filtering: disabled/no-op unchanged")

    def _accumulate_dry_run_table_deltas(self, *, summary: LinkedRelatedEnrichmentSummary, before, populated: dict[str, int]) -> None:
        for table, created_attr, reused_attr in [
            ("article_prd", "article_prd_rows_created", "article_prd_rows_reused"),
            ("article_links", "article_links_rows_created", "article_links_rows_reused"),
            ("prd", "prd_rows_created", "prd_rows_reused"),
        ]:
            incoming = int(populated.get(table, 0))
            if incoming <= 0:
                continue
            before_count = self._state_count(state=before, table=table)
            created = max(incoming - before_count, 0)
            reused = max(min(incoming, before_count), 0)
            setattr(summary, created_attr, int(getattr(summary, created_attr)) + created)
            setattr(summary, reused_attr, int(getattr(summary, reused_attr)) + reused)

    def _accumulate_real_table_deltas(self, *, summary: LinkedRelatedEnrichmentSummary, before, after, populated: dict[str, int]) -> None:
        for table, created_attr, reused_attr in [
            ("article_prd", "article_prd_rows_created", "article_prd_rows_reused"),
            ("article_links", "article_links_rows_created", "article_links_rows_reused"),
            ("prd", "prd_rows_created", "prd_rows_reused"),
        ]:
            before_count = self._state_count(state=before, table=table)
            after_count = self._state_count(state=after, table=table)
            created = max(after_count - before_count, 0)
            incoming = int(populated.get(table, 0))
            reused = max(incoming - created, 0)
            setattr(summary, created_attr, int(getattr(summary, created_attr)) + created)
            setattr(summary, reused_attr, int(getattr(summary, reused_attr)) + reused)

    def _state_count(self, *, state, table: str) -> int:
        if table == "article_prd":
            return int(state.article_prd_rows)
        if table == "article_links":
            return int(state.article_links_rows)
        if table == "prd":
            return int(state.prd_rows)
        return 0

    def _safe_int(self, value) -> int | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
