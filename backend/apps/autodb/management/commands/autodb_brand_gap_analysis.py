from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.brand_gap_analysis import AutoDbBrandGapAnalysisService


class Command(BaseCommand):
    help = "Read-only Auto_DB brand gap analysis through matching service."

    def handle(self, *args, **options):
        payload = AutoDbBrandGapAnalysisService().run()
        self.stdout.write("Done")
        self.stdout.write(f"coverage_rows={len(payload.get('coverage_rows', []))}")
        self.stdout.write(f"blocked_needs_alias_rows={len(payload.get('blocked_rows', []))}")
        self.stdout.write(f"prioritized_missing_rows={len(payload.get('prioritized_rows', []))}")
        self.stdout.write(f"unsafe_rows={len(payload.get('unsafe_rows', []))}")
