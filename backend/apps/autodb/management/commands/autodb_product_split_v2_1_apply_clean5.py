from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.product_split_v2_1_apply_clean5 import AutoDbProductSplitV21ApplyClean5Service


class Command(BaseCommand):
    help = "Apply up to 5 clean split v2.1 candidates with full baseline/dry-run/verification reporting."

    def handle(self, *args, **options):
        payload = AutoDbProductSplitV21ApplyClean5Service().run()
        self.stdout.write("Done")
        self.stdout.write(f"selected_count={payload.get('selected_count', 0)}")
        self.stdout.write(f"final_dry_count={payload.get('final_dry_count', 0)}")
        self.stdout.write(f"applied_count={payload.get('applied_count', 0)}")
        self.stdout.write(f"skipped_count={payload.get('skipped_count', 0)}")
