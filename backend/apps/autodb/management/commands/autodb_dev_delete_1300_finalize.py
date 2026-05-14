from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.dev_delete_1300_finalize import AutoDbDevDelete1300FinalizeService


class Command(BaseCommand):
    help = "Finalize dev delete+GPL import workflow: rebuild queue and write final report files."

    def handle(self, *args, **options):
        payload = AutoDbDevDelete1300FinalizeService().run()
        self.stdout.write(self.style.SUCCESS("Done"))
        self.stdout.write(f"queue_run_id={payload.get('queue_run_id', '')}")
        self.stdout.write(f"queue_rows={payload.get('queue_rows', 0)}")
