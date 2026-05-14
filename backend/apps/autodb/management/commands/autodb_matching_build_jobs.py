from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand

from apps.autodb.management.commands._matching_common import MatchingCommandMixin
from apps.autodb.services.matching import AutoDbMatchJobBuilder, AutoDbMatchingPipelineService


class Command(MatchingCommandMixin, BaseCommand):
    help = "Build persistent Auto_DB matching jobs from latest supplier offers."
    command_name = "autodb_matching_build_jobs"

    def add_arguments(self, parser):
        self.add_common_arguments(parser, default_limit=100, dry_run_default=True)
        parser.add_argument("--supplier-code", type=str, default="")
        parser.add_argument("--fast-mode", action="store_true", default=False)
        parser.add_argument("--pre-gate", action="store_true", default=False)
        parser.add_argument("--pre-gate-size", type=int, default=20)
        parser.add_argument("--pre-gate-build-limit", type=int, default=1000)
        parser.add_argument("--pre-gate-min-probe-n", type=int, default=20)
        parser.add_argument("--pre-gate-min-hit-rate", type=float, default=20.0)

    def handle(self, *args, **options):
        run = self.start_run(run_type=self.command_name, dry_run=bool(options["dry_run"]))
        try:
            supplier_code = str(options.get("supplier_code") or "").strip()
            fast_mode = bool(options.get("fast_mode"))
            pre_gate_enabled = bool(options.get("pre_gate"))
            pipeline = AutoDbMatchingPipelineService(
                job_builder=AutoDbMatchJobBuilder(fast_mode=fast_mode)
            )
            pre_gate_result = None
            if pre_gate_enabled:
                pre_gate_result = pipeline.pre_gate_build_candidates(
                    supplier_code=supplier_code,
                    build_limit=int(options.get("pre_gate_build_limit") or 1000),
                    sample_size=int(options.get("pre_gate_size") or 20),
                    min_probe_n=int(options.get("pre_gate_min_probe_n") or 20),
                    min_hit_rate_pct=float(options.get("pre_gate_min_hit_rate") or 20.0),
                )
            if pre_gate_result is not None and pre_gate_result.would_stop:
                rows = []
            else:
                rows = pipeline.build_jobs(
                    run=run,
                    supplier_code=supplier_code,
                    limit=int(options["limit"]),
                    dry_run=bool(options["dry_run"]),
                    fast_mode=fast_mode,
                )
            rows_count = len(rows)
            by_supplier = Counter(row.supplier_code or "-" for row in rows)
            by_brand = Counter(row.normalized_brand or "-" for row in rows)
            by_resolver_source = Counter((row.resolver_source or "unresolved") for row in rows)
            by_article_source = Counter((row.article_source_type or "-") for row in rows)
            by_reason = Counter((row.reason or "-") for row in rows)
            by_status = Counter((row.status or "-") for row in rows)
            paused_statuses = {
                "skipped_non_tecdoc",
                "skipped_brand_unresolved",
                "skipped_split_needed",
                "skipped_unsafe_ambiguous",
                "skipped_bad_article_source",
                "quota_paused",
            }
            paused_buckets = {key: count for key, count in by_status.items() if key in paused_statuses}
            csv_path, md_path, rows_count = self.export(
                run=run,
                rows=rows,
                title="Auto_DB Matching Job Build",
                export_prefix=str(options.get("export_prefix") or ""),
                supplier_code=supplier_code,
                fast_mode=fast_mode,
                pre_gate_enabled=pre_gate_enabled,
                pre_gate_checked=(pre_gate_result.checked if pre_gate_result else 0),
                pre_gate_hits=(pre_gate_result.hits if pre_gate_result else 0),
                pre_gate_candidate_count=(pre_gate_result.candidate_count if pre_gate_result else 0),
                pre_gate_hit_rate_pct=(pre_gate_result.hit_rate_pct if pre_gate_result else 0.0),
                pre_gate_min_probe_n=(pre_gate_result.min_probe_n if pre_gate_result else int(options.get("pre_gate_min_probe_n") or 20)),
                pre_gate_min_hit_rate_pct=(
                    pre_gate_result.min_hit_rate_pct if pre_gate_result else float(options.get("pre_gate_min_hit_rate") or 20.0)
                ),
                pre_gate_can_continue=(pre_gate_result.can_continue if pre_gate_result else False),
                pre_gate_would_stop=(pre_gate_result.would_stop if pre_gate_result else False),
                pre_gate_reason=(pre_gate_result.reason if pre_gate_result else ""),
                skipped_missing_supplier_id=(pre_gate_result.skipped_missing_supplier_id if pre_gate_result else 0),
                queue_size=rows_count,
                rows_by_supplier_code=dict(by_supplier),
                rows_by_brand_top_50=dict(by_brand.most_common(50)),
                rows_by_resolver_source=dict(by_resolver_source),
                rows_by_article_source=dict(by_article_source),
                rows_by_reason=dict(by_reason),
                rows_by_status=dict(by_status),
                paused_buckets=paused_buckets,
            )
            self.finish_run(
                run,
                rows_count=rows_count,
                supplier_code=supplier_code,
                fast_mode=fast_mode,
                pre_gate_enabled=pre_gate_enabled,
                pre_gate_would_stop=(pre_gate_result.would_stop if pre_gate_result else False),
                pre_gate_hits=(pre_gate_result.hits if pre_gate_result else 0),
                pre_gate_hit_rate_pct=(pre_gate_result.hit_rate_pct if pre_gate_result else 0.0),
                pre_gate_reason=(pre_gate_result.reason if pre_gate_result else ""),
            )
            self.stdout.write(f"Exported: {csv_path}")
            self.stdout.write(f"Exported: {md_path}")
        except Exception as exc:  # noqa: BLE001
            self.fail_run(run, exc)
            raise
