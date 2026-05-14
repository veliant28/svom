from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.product_split_v2_1_validator import AutoDbProductSplitV21Validator


class Command(BaseCommand):
    help = "Run split v2.1 pre-apply validator dry-run on known cases and remaining candidates."

    def handle(self, *args, **options):
        validator = AutoDbProductSplitV21Validator()
        result = validator.run()
        known = result.get("known_summary", {})
        remaining = result.get("remaining_summary", {})

        self.stdout.write("OK")
        self.stdout.write(
            f"known_cases_checked={known.get('known_cases_checked', 0)} "
            f"known_blocked={known.get('blocked', 0)} "
            f"remaining_checked={remaining.get('total_checked', 0)} "
            f"remaining_clean={remaining.get('clean', 0)} "
            f"remaining_blocked={remaining.get('blocked', 0)}"
        )
        self.stdout.write(f"known_csv={validator.OUT_KNOWN_CSV}")
        self.stdout.write(f"known_md={validator.OUT_KNOWN_MD}")
        self.stdout.write(f"remaining_csv={validator.OUT_REMAINING_CSV}")
        self.stdout.write(f"remaining_md={validator.OUT_REMAINING_MD}")
        self.stdout.write(f"final_report={validator.OUT_FINAL_MD}")
