from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.product_split_v2_post_pilots_queue import AutoDbProductSplitV2PostPilotsQueueService


class Command(BaseCommand):
    help = "Rebuild quality queue and reconcile service state after successful split v2 pilots."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run-reconciliation", action="store_true", default=False)

    def handle(self, *args, **options):
        apply_reconciliation = not bool(options.get("dry_run_reconciliation"))
        payload = AutoDbProductSplitV2PostPilotsQueueService().run(apply_reconciliation=apply_reconciliation)
        self.stdout.write("Done")
        self.stdout.write(f"apply_reconciliation={apply_reconciliation}")
        self.stdout.write(f"pilots={len(payload.get('pilots', []))}")
        self.stdout.write(f"queue_size={payload.get('queue_summary', {}).get('queue_size', 0)}")
        self.stdout.write(f"reconciliation_applied={payload.get('reconciliation_apply_summary', {}).get('applied', 0)}")

