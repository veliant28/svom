from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.management.commands._matching_common import MatchingCommandMixin
from apps.autodb.services.matching import AutoDbMatchingPipelineService


class Command(MatchingCommandMixin, BaseCommand):
    help = "Plan Auto_DB local clone sync. article_images are explicitly disabled."
    command_name = "autodb_matching_plan_clone_sync"

    def add_arguments(self, parser):
        self.add_common_arguments(parser, default_limit=100, dry_run_default=True)

    def handle(self, *args, **options):
        run = self.start_run(run_type=self.command_name, dry_run=bool(options["dry_run"]))
        try:
            rows = AutoDbMatchingPipelineService().plan_clone_sync(run=run, limit=int(options["limit"]), dry_run=bool(options["dry_run"]))
            csv_path, md_path, rows_count = self.export(
                run=run,
                rows=rows,
                title="Auto_DB Matching Clone Sync Plan",
                export_prefix=str(options.get("export_prefix") or ""),
                images_disabled=True,
            )
            self.finish_run(run, rows_count=rows_count, images_disabled=True)
            self.stdout.write(f"Exported: {csv_path}")
            self.stdout.write(f"Exported: {md_path}")
        except Exception as exc:  # noqa: BLE001
            self.fail_run(run, exc)
            raise
