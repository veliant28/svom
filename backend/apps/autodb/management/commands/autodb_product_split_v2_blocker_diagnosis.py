from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.product_split_v2_blocker_diagnosis import AutoDbProductSplitV2BlockerDiagnosisService


class Command(BaseCommand):
    help = "Diagnose split v2 batch blockers and search clean resolved-brand split candidates (dry-run only)."

    def add_arguments(self, parser):
        parser.add_argument("--max-batch-size", type=int, default=20)

    def handle(self, *args, **options):
        max_batch_size = int(options.get("max_batch_size") or 20)
        payload = AutoDbProductSplitV2BlockerDiagnosisService().run(max_batch_size=max_batch_size)
        dry_summary = payload.get("dry_summary", {})
        self.stdout.write("Done")
        self.stdout.write(f"max_batch_size={max_batch_size}")
        self.stdout.write(f"blocked_diagnosed={len(payload.get('blocked_rows', []))}")
        self.stdout.write(f"search_rows={len(payload.get('search_rows', []))}")
        self.stdout.write(f"dry_checked={dry_summary.get('checked', 0)}")
        self.stdout.write(f"dry_clean={dry_summary.get('clean', 0)}")

