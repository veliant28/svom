from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.dev_delete_1300_gpl_import import AutoDbDevDelete1300AndFreshGplImportService


class Command(BaseCommand):
    help = "Dev-only hard delete quarantined multi-offer conflict products and run fresh GPL import pipeline."

    def handle(self, *args, **options):
        payload = AutoDbDevDelete1300AndFreshGplImportService().run()
        self.stdout.write(self.style.SUCCESS("Done"))
        self.stdout.write(f"scope_count={payload.get('scope_count', 0)}")
        self.stdout.write(f"delete_products={payload.get('delete_products', 0)}")
        self.stdout.write(f"gpl_dry_run_id={payload.get('gpl_dry_run_id', '')}")
        self.stdout.write(f"gpl_apply_run_id={payload.get('gpl_apply_run_id', '')}")
        self.stdout.write(f"queue_rows={payload.get('queue_rows', 0)}")
