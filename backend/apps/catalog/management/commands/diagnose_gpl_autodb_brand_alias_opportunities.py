from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services import AutoDbBrandAliasDiagnosticsService


class Command(BaseCommand):
    help = "Read-only GPL brand alias opportunity diagnostics for Auto_DB supplier resolution."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True)
        parser.add_argument("--limit", type=int, default=20000)
        parser.add_argument("--export-csv", type=str, required=True)

    def handle(self, *args, **options):
        supplier = str(options["supplier"] or "").strip().lower()
        if supplier != "gpl":
            raise CommandError("This command currently supports only --supplier GPL.")
        limit = max(int(options.get("limit") or 0), 0)
        export_path = Path(str(options["export_csv"]).strip()).expanduser()

        service = AutoDbBrandAliasDiagnosticsService()
        stats = service.collect_brand_stats(
            supplier_code=supplier,
            all_suppliers=False,
            limit=limit,
            brand_filters=set(),
        )
        rows = service.diagnose(stats=stats, min_confidence=0.9)

        out: list[dict[str, str]] = []
        for item in rows:
            candidate_list = item.candidates or ""
            possible_matches = "0"
            if candidate_list:
                possible_matches = str(len([chunk for chunk in candidate_list.split(";") if chunk.strip()]))

            confidence = float(item.confidence or 0.0)
            can_auto_confirm = (
                item.recommendation == "create_alias"
                and bool(item.recommended_supplier_id)
                and confidence >= 0.9
            )

            out.append(
                {
                    "raw_brand": item.raw_brand,
                    "product_count": str(item.offers),
                    "exact_local_supplier_name_candidates": "1" if item.exact_supplier_match else "0",
                    "fuzzy_supplier_candidates": str(item.relaxed_candidates),
                    "supplier_detail_candidates": possible_matches,
                    "confidence": f"{confidence:.2f}",
                    "can_auto_confirm": "1" if can_auto_confirm else "0",
                    "reason": item.reason,
                    "recommended_action": item.recommendation,
                    "proposed_supplier_id": str(item.recommended_supplier_id or ""),
                    "proposed_supplier_name": item.recommended_supplier_name,
                    "examples": item.sample_articles,
                    "possible_supplier_matches": candidate_list,
                }
            )

        self._write_csv(export_path=export_path, rows=out)

        self.stdout.write("diagnose_gpl_autodb_brand_alias_opportunities summary:")
        self.stdout.write(f"- rows: {len(out)}")
        self.stdout.write(f"- can_auto_confirm: {sum(1 for row in out if row['can_auto_confirm'] == '1')}")
        self.stdout.write(f"- manual_review: {sum(1 for row in out if row['recommended_action'] == 'manual_review')}")
        self.stdout.write(f"- csv: {export_path}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- writes=0")

    @staticmethod
    def _write_csv(*, export_path: Path, rows: list[dict[str, str]]) -> None:
        export_path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "raw_brand",
            "product_count",
            "exact_local_supplier_name_candidates",
            "fuzzy_supplier_candidates",
            "supplier_detail_candidates",
            "confidence",
            "can_auto_confirm",
            "reason",
            "recommended_action",
            "proposed_supplier_id",
            "proposed_supplier_name",
            "examples",
            "possible_supplier_matches",
        ]
        with export_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in headers})
