from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.management.commands._matching_common import MatchingCommandMixin
from apps.autodb.models import AutoDbMatchJob
from apps.autodb.services.matching import AutoDbEnrichmentPlanner


class Command(MatchingCommandMixin, BaseCommand):
    help = "Guarded fitments apply command skeleton. Requires --apply; images disabled."
    command_name = "autodb_matching_apply_fitments"

    def add_arguments(self, parser):
        self.add_common_arguments(parser, default_limit=100, dry_run_default=False)
        parser.add_argument("--apply", action="store_true", default=False)

    def handle(self, *args, **options):
        self.require_apply(options)
        run = self.start_run(run_type=self.command_name, dry_run=False)
        try:
            jobs = AutoDbMatchJob.objects.filter(
                status__in=[AutoDbMatchJob.STATUS_LINKED, AutoDbMatchJob.STATUS_SAFE_LINK_CANDIDATE]
            ).order_by("priority", "created_at")[: max(int(options["limit"]), 1)]
            rows = AutoDbEnrichmentPlanner().apply_fitments(jobs, apply=True)
            csv_path, md_path, rows_count = self.export(
                run=run,
                rows=rows,
                title="Auto_DB Matching Fitments Apply Gate",
                export_prefix=str(options.get("export_prefix") or ""),
                product_writes=False,
                foundation_note="foundation command does not apply enrichment",
            )
            self.finish_run(run, rows_count=rows_count, product_writes=False, apply_gate_only=True)
            self.stdout.write(f"Exported: {csv_path}")
            self.stdout.write(f"Exported: {md_path}")
        except Exception as exc:  # noqa: BLE001
            self.fail_run(run, exc)
            raise
