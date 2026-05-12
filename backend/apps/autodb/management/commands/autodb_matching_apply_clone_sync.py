from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.management.commands._matching_common import MatchingCommandMixin
from apps.autodb.services.matching import AutoDbMatchingPipelineService


class Command(MatchingCommandMixin, BaseCommand):
    help = "Guarded clone sync apply command skeleton. Requires --apply; article_images remain disabled."
    command_name = "autodb_matching_apply_clone_sync"

    def add_arguments(self, parser):
        self.add_common_arguments(parser, default_limit=100, dry_run_default=False)
        parser.add_argument("--apply", action="store_true", default=False)

    def handle(self, *args, **options):
        self.require_apply(options)
        run = self.start_run(run_type=self.command_name, dry_run=False)
        try:
            rows = AutoDbMatchingPipelineService().plan_clone_sync(run=run, limit=int(options["limit"]), dry_run=False)
            csv_path, md_path, rows_count = self.export(
                run=run,
                rows=rows,
                title="Auto_DB Matching Clone Sync Apply Gate",
                export_prefix=str(options.get("export_prefix") or ""),
                images_disabled=True,
                foundation_note="actual clone row upsert is not executed by foundation command",
            )
            self.finish_run(run, rows_count=rows_count, images_disabled=True, apply_gate_only=True)
            self.stdout.write(f"Exported: {csv_path}")
            self.stdout.write(f"Exported: {md_path}")
        except Exception as exc:  # noqa: BLE001
            self.fail_run(run, exc)
            raise
