from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.management.commands._matching_common import MatchingCommandMixin
from apps.autodb.services.matching import AutoDbMatchingPipelineService


class Command(MatchingCommandMixin, BaseCommand):
    help = "Run quota-aware remote Auto_DB lookup for remote_pending jobs. No local clone upserts."
    command_name = "autodb_matching_run_remote"

    def add_arguments(self, parser):
        self.add_common_arguments(parser, default_limit=300, dry_run_default=True)

    def handle(self, *args, **options):
        run = self.start_run(run_type=self.command_name, dry_run=bool(options["dry_run"]))
        try:
            rows = AutoDbMatchingPipelineService().run_remote(run=run, limit=int(options["limit"]), dry_run=bool(options["dry_run"]))
            stopped_on_quota = any(getattr(row, "status", "") == "quota_paused" for row in rows)
            csv_path, md_path, rows_count = self.export(
                run=run,
                rows=rows,
                title="Auto_DB Matching Remote Lookup",
                export_prefix=str(options.get("export_prefix") or ""),
                stopped_on_quota=stopped_on_quota,
            )
            self.finish_run(run, rows_count=rows_count, stopped_on_quota=stopped_on_quota)
            self.stdout.write(f"Exported: {csv_path}")
            self.stdout.write(f"Exported: {md_path}")
        except Exception as exc:  # noqa: BLE001
            self.fail_run(run, exc)
            raise
