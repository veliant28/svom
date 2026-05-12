from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.management.commands._matching_common import MatchingCommandMixin
from apps.autodb.services.matching import AutoDbMatchingPipelineService


class Command(MatchingCommandMixin, BaseCommand):
    help = "Run local-only deterministic Auto_DB lookup for matching jobs."
    command_name = "autodb_matching_run_local"

    def add_arguments(self, parser):
        self.add_common_arguments(parser, default_limit=100, dry_run_default=True)

    def handle(self, *args, **options):
        run = self.start_run(run_type=self.command_name, dry_run=bool(options["dry_run"]))
        try:
            rows = AutoDbMatchingPipelineService().run_local(run=run, limit=int(options["limit"]), dry_run=bool(options["dry_run"]))
            csv_path, md_path, rows_count = self.export(
                run=run,
                rows=rows,
                title="Auto_DB Matching Local Lookup",
                export_prefix=str(options.get("export_prefix") or ""),
            )
            self.finish_run(run, rows_count=rows_count)
            self.stdout.write(f"Exported: {csv_path}")
            self.stdout.write(f"Exported: {md_path}")
        except Exception as exc:  # noqa: BLE001
            self.fail_run(run, exc)
            raise
