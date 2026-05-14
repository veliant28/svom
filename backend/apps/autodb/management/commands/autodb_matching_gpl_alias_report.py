from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.autodb.services.supplier_brand_matcher import SupplierBrandMatcher
from apps.supplier_imports.parsers.utils import normalize_brand


@dataclass(frozen=True)
class AliasProposal:
    raw_brand: str
    recommendation: str
    expected_supplier_id: str
    expected_supplier_name: str
    note: str


class Command(BaseCommand):
    help = "Generate report-only GPL brand alias proposals (no DB writes)."

    CONFIRMED_LOOKING: tuple[AliasProposal, ...] = (
        AliasProposal("WIX FILTERS", "confirmed_looking", "324", "WIX FILTERS", "high confidence candidate"),
        AliasProposal("BOSAL", "confirmed_looking", "41", "BOSAL", "high confidence candidate"),
        AliasProposal("SPIDAN", "confirmed_looking", "1", "SPIDAN", "high confidence candidate"),
        AliasProposal("POLMO", "confirmed_looking", "4873", "POLMO", "high confidence candidate"),
    )
    MANUAL_REVIEW_ONLY: tuple[AliasProposal, ...] = (
        AliasProposal("ALCA", "manual_review_only", "4664", "Metalcaucho", "possible mismatch; requires manual review"),
        AliasProposal(
            "ALPHA FILTER",
            "manual_review_only",
            "",
            "",
            "ambiguous candidates (e.g. MANN/HENGST/AMC/CLEAN/ALCO); do not auto-apply",
        ),
    )

    def add_arguments(self, parser):
        parser.add_argument("--export-csv", type=str, default="/tmp/gpl_alias_report_only_workflow.csv")
        parser.add_argument("--export-md", type=str, default="/tmp/gpl_alias_report_only_workflow.md")

    def handle(self, *args, **options):
        export_csv = Path(str(options.get("export_csv") or "/tmp/gpl_alias_report_only_workflow.csv")).expanduser()
        export_md = Path(str(options.get("export_md") or "/tmp/gpl_alias_report_only_workflow.md")).expanduser()
        rows = self._build_rows()
        self._write_csv(export_csv, rows)
        self._write_md(export_md, rows)
        self.stdout.write(f"CSV export: {export_csv}")
        self.stdout.write(f"MD export: {export_md}")
        self.stdout.write("mode=report_only")
        self.stdout.write("db_writes=0")

    def _build_rows(self) -> list[dict[str, str]]:
        matcher = SupplierBrandMatcher()
        out: list[dict[str, str]] = []
        proposals = [*self.CONFIRMED_LOOKING, *self.MANUAL_REVIEW_ONLY]
        for item in proposals:
            normalized = normalize_brand(item.raw_brand)
            result = matcher.resolve_many([normalized]).get(normalized)
            top = result.candidates[0] if result and result.candidates else None
            top_supplier_id = str(top.supplier_id) if top is not None else ""
            top_supplier_name = str(top.supplier_description or top.supplier_matchcode or "") if top is not None else ""
            top_confidence = f"{float(top.confidence):.2f}" if top is not None else "0.00"
            top_reason = str(top.reason or "") if top is not None else "no_candidate"
            candidates = ""
            if result and result.candidates:
                candidates = "; ".join(
                    f"{c.supplier_id}:{c.supplier_description or c.supplier_matchcode}:{float(c.confidence):.2f}:{c.reason}"
                    for c in result.candidates[:5]
                )
            out.append(
                {
                    "raw_brand": item.raw_brand,
                    "normalized_brand": normalized,
                    "recommendation": item.recommendation,
                    "expected_supplier_id": item.expected_supplier_id,
                    "expected_supplier_name": item.expected_supplier_name,
                    "matcher_top_supplier_id": top_supplier_id,
                    "matcher_top_supplier_name": top_supplier_name,
                    "matcher_top_confidence": top_confidence,
                    "matcher_top_reason": top_reason,
                    "candidates_top5": candidates,
                    "note": item.note,
                    "report_only": "1",
                }
            )
        return out

    def _write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "raw_brand",
            "normalized_brand",
            "recommendation",
            "expected_supplier_id",
            "expected_supplier_name",
            "matcher_top_supplier_id",
            "matcher_top_supplier_name",
            "matcher_top_confidence",
            "matcher_top_reason",
            "candidates_top5",
            "note",
            "report_only",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _write_md(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# GPL alias report-only workflow",
            "",
            "- Mode: report-only (no DB writes).",
            "- Confirmed-looking rows are suggestions only; manual approval required before any apply command.",
            "",
            "| raw_brand | recommendation | expected | matcher top | confidence | reason |",
            "|---|---|---|---|---:|---|",
        ]
        for row in rows:
            expected = f"{row.get('expected_supplier_id') or '-'} {row.get('expected_supplier_name') or ''}".strip()
            matcher_top = f"{row.get('matcher_top_supplier_id') or '-'} {row.get('matcher_top_supplier_name') or ''}".strip()
            lines.append(
                f"| {row.get('raw_brand') or '-'} | {row.get('recommendation') or '-'} | {expected or '-'} | "
                f"{matcher_top or '-'} | {row.get('matcher_top_confidence') or '0.00'} | {row.get('matcher_top_reason') or '-'} |"
            )
        lines.extend(
            [
                "",
                "## Safety",
                "",
                "- No alias upsert/create/update executed.",
                "- No Product/price/stock writes.",
                "- No sync/import/enrichment/UTR API.",
            ]
        )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
