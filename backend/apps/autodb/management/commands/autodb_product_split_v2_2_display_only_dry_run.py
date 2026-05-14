from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.product_split_v2_2_display_only import (
    AutoDbProductSplitV22DisplayOnlyDryRunService,
)


class Command(BaseCommand):
    help = "Run split v2.2 display-only planner/validator dry-run and export reports."

    def handle(self, *args, **options):
        payload = AutoDbProductSplitV22DisplayOnlyDryRunService().run()
        summary = payload.get("dry_summary", {})

        self.stdout.write("Done")
        self.stdout.write(f"checked={summary.get('checked', 0)}")
        self.stdout.write(f"display_only_clean={summary.get('display_only_clean', 0)}")
        self.stdout.write(f"blocked={summary.get('blocked', 0)}")
        self.stdout.write("reports=/tmp/product_quality_split_v2_2_display_only_*")
