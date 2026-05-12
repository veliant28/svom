from __future__ import annotations

from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.brand_coverage import AutoDbBrandCoverageAuditService
from apps.autodb.services.matching.reports import write_csv, write_md


class Command(BaseCommand):
    help = "Audit raw brand groups for 100% TecDoc decision coverage."

    def add_arguments(self, parser):
        parser.add_argument("--supplier-code", type=str, default="")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--csv-out", type=str, default="/tmp/autodb_brand_coverage_audit.csv")
        parser.add_argument("--md-out", type=str, default="/tmp/autodb_brand_coverage_audit.md")

    def handle(self, *args, **options):
        rows = AutoDbBrandCoverageAuditService().audit(
            supplier_code=str(options.get("supplier_code") or "").strip(),
            limit=int(options.get("limit") or 0),
        )
        by_decision = Counter(row.decision for row in rows)
        missing_rows = [
            row
            for row in rows
            if row.decision in {"keep_unmapped_missing_supplier", "needs_human_approval", "unsafe_ambiguous", "split_brand_needed"}
        ]
        missing_rows.sort(key=lambda item: item.product_count, reverse=True)
        csv_path = Path(str(options["csv_out"])).expanduser()
        md_path = Path(str(options["md_out"])).expanduser()
        rows_count = write_csv(csv_path, [row.__dict__ for row in rows])
        write_md(
            md_path,
            title="Auto_DB Brand Coverage Audit",
            summary={
                "supplier_code": options.get("supplier_code") or "",
                "coverage_definition": "every TecDoc-eligible brand has a decision/action, not blind aliasing",
                "total_brand_groups": rows_count,
                "mapped": by_decision.get("mapped", 0),
                "needs_alias": by_decision.get("needs_alias", 0),
                "non_tecdoc": by_decision.get("non_tecdoc", 0),
                "keep_unmapped_missing_supplier": by_decision.get("keep_unmapped_missing_supplier", 0),
                "split_brand_needed": by_decision.get("split_brand_needed", 0),
                "unsafe_ambiguous": by_decision.get("unsafe_ambiguous", 0),
                "needs_human_approval": by_decision.get("needs_human_approval", 0),
                "top_remaining_missing_supplier_rows": [
                    f"{item.supplier_code}:{item.raw_brand}:{item.product_count}:{item.local_autodb_candidate}"
                    for item in missing_rows[:25]
                ],
            },
            csv_path=csv_path,
            rows_count=rows_count,
        )
        self.stdout.write(f"Exported: {csv_path}")
        self.stdout.write(f"Exported: {md_path}")
