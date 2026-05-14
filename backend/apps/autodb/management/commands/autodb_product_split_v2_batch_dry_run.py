from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.product_split_v2_batch_dry_run import AutoDbProductSplitV2BatchDryRunService


class Command(BaseCommand):
    help = "Prepare small split v2 batch dry-run package for obvious multi-offer split candidates."

    def add_arguments(self, parser):
        parser.add_argument("--max-candidates", type=int, default=20)
        parser.add_argument("--prefer-top", type=int, default=10)

    def handle(self, *args, **options):
        max_candidates = int(options.get("max_candidates") or 20)
        prefer_top = int(options.get("prefer_top") or 10)
        payload = AutoDbProductSplitV2BatchDryRunService().run(max_candidates=max_candidates, prefer_top=prefer_top)
        readiness = payload.get("readiness", {})

        self.stdout.write("Done")
        self.stdout.write(f"max_candidates={max_candidates}")
        self.stdout.write(f"prefer_top={prefer_top}")
        self.stdout.write(f"selected_candidates={readiness.get('selected_candidates', 0)}")
        self.stdout.write(f"clean_candidates={readiness.get('clean_candidates', 0)}")
        self.stdout.write("reports=/tmp/product_quality_split_v2_batch_*")

