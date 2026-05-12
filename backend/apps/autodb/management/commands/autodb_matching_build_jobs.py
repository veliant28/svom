from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand

from apps.autodb.management.commands._matching_common import MatchingCommandMixin
from apps.autodb.services.matching import AutoDbMatchJobBuilder


class Command(MatchingCommandMixin, BaseCommand):
    help = "Build persistent Auto_DB matching jobs from latest supplier offers."
    command_name = "autodb_matching_build_jobs"

    def add_arguments(self, parser):
        self.add_common_arguments(parser, default_limit=100, dry_run_default=True)
        parser.add_argument("--supplier-code", type=str, default="")

    def handle(self, *args, **options):
        run = self.start_run(run_type=self.command_name, dry_run=bool(options["dry_run"]))
        try:
            rows = AutoDbMatchJobBuilder().build_jobs(
                run=run,
                supplier_code=str(options.get("supplier_code") or "").strip(),
                limit=int(options["limit"]),
                dry_run=bool(options["dry_run"]),
            )
            rows_count = len(rows)
            by_supplier = Counter(row.supplier_code or "-" for row in rows)
            by_brand = Counter(row.normalized_brand or "-" for row in rows)
            by_resolver_source = Counter((row.resolver_source or "unresolved") for row in rows)
            by_article_source = Counter((row.article_source_type or "-") for row in rows)
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
                supplier_code=options.get("supplier_code") or "",
                queue_size=rows_count,
                rows_by_supplier_code=dict(by_supplier),
                rows_by_brand_top_50=dict(by_brand.most_common(50)),
                rows_by_resolver_source=dict(by_resolver_source),
                rows_by_article_source=dict(by_article_source),
                rows_by_status=dict(by_status),
                paused_buckets=paused_buckets,
            )
            self.finish_run(run, rows_count=rows_count, supplier_code=options.get("supplier_code") or "")
            self.stdout.write(f"Exported: {csv_path}")
            self.stdout.write(f"Exported: {md_path}")
        except Exception as exc:  # noqa: BLE001
            self.fail_run(run, exc)
            raise
