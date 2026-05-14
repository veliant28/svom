from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.tecdoc_gap_binding import AutoDbTecdocGapBindingService


class Command(BaseCommand):
    help = "Resolve remaining TecDoc-like brand gaps through Auto_DB Matching Service."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", default=False)
        parser.add_argument("--queue-limit", type=int, default=2000)

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        queue_limit = int(options.get("queue_limit") or 2000)
        payload = AutoDbTecdocGapBindingService().run(apply_changes=apply_changes, queue_limit=queue_limit)

        self.stdout.write("Done")
        self.stdout.write(f"apply_changes={apply_changes}")
        self.stdout.write(f"queue_limit={queue_limit}")
        self.stdout.write(f"coverage_before_rows={len(payload.get('coverage_before', []))}")
        self.stdout.write(f"coverage_after_rows={len(payload.get('coverage_after', []))}")
