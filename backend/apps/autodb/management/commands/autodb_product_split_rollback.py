from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.matching import AutoDbProductSplitRollbackService


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return repr(value)
    return str(value)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["result"])
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _stringify(row.get(key)) for key in fields})


def _write_md(path: Path, *, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([f"# {title}", "", *lines, ""]), encoding="utf-8")


class Command(BaseCommand):
    help = "Service-backed rollback for one pilot split (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--source-product-id", type=str, required=True)
        parser.add_argument("--split-product-id", type=str, required=True)
        parser.add_argument("--moved-offer-id", action="append", dest="moved_offer_ids", default=[])
        parser.add_argument("--moved-raw-offer-id", action="append", dest="moved_raw_offer_ids", default=[])
        parser.add_argument("--split-productprice-id", action="append", dest="split_productprice_ids", default=[])
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--apply", action="store_true", default=False)
        parser.add_argument("--export-prefix", type=str, default="/tmp/autodb_product_split_rollback")

    def handle(self, *args, **options):
        source_product_id = str(options.get("source_product_id") or "").strip()
        split_product_id = str(options.get("split_product_id") or "").strip()
        moved_offer_ids = [str(item or "").strip() for item in options.get("moved_offer_ids") or [] if str(item or "").strip()]
        moved_raw_offer_ids = [str(item or "").strip() for item in options.get("moved_raw_offer_ids") or [] if str(item or "").strip()]
        split_productprice_ids = [str(item or "").strip() for item in options.get("split_productprice_ids") or [] if str(item or "").strip()]
        apply_mode = bool(options.get("apply"))
        if not source_product_id or not split_product_id:
            raise CommandError("--source-product-id and --split-product-id are required")
        if not moved_offer_ids:
            raise CommandError("--moved-offer-id is required at least once")

        service = AutoDbProductSplitRollbackService()
        prefix = Path(str(options.get("export_prefix") or "/tmp/autodb_product_split_rollback"))
        csv_path = prefix.with_suffix(".csv")
        md_path = prefix.with_suffix(".md")

        if apply_mode:
            result = service.apply(
                source_product_id=source_product_id,
                split_product_id=split_product_id,
                moved_offer_ids=moved_offer_ids,
                moved_raw_offer_ids=moved_raw_offer_ids,
                split_productprice_ids=split_productprice_ids,
            )
            row = asdict(result)
            _write_csv(csv_path, [row])
            lines = [
                "- mode: apply",
                f"- source_product_id: {row.get('source_product_id','')}",
                f"- split_product_id: {row.get('split_product_id','')}",
                f"- moved_offer_ids_restored: {row.get('moved_offer_ids_restored','')}",
                f"- moved_raw_offer_ids_restored: {row.get('moved_raw_offer_ids_restored','')}",
                f"- split_productprice_ids_removed: {row.get('split_productprice_ids_removed','')}",
                f"- split_product_action: {row.get('split_product_action','')}",
                f"- source_display_brand_after: {row.get('source_display_brand_after','')}",
                f"- source_autodb_supplier_id_after: {row.get('source_autodb_supplier_id_after','')}",
                f"- source_offer_count_after: {row.get('source_offer_count_after','')}",
                f"- split_offer_count_after: {row.get('split_offer_count_after','')}",
                f"- csv: {csv_path}",
            ]
            _write_md(md_path, title="AutoDB product split rollback apply", lines=lines)
            self.stdout.write("APPLY_OK")
            self.stdout.write(f"csv={csv_path}")
            self.stdout.write(f"md={md_path}")
            return

        plan = service.plan(
            source_product_id=source_product_id,
            split_product_id=split_product_id,
            moved_offer_ids=moved_offer_ids,
            moved_raw_offer_ids=moved_raw_offer_ids,
            split_productprice_ids=split_productprice_ids,
        )
        row = asdict(plan)
        _write_csv(csv_path, [row])
        lines = [
            "- mode: dry_run",
            f"- source_product_id: {row.get('source_product_id','')}",
            f"- split_product_id: {row.get('split_product_id','')}",
            f"- requested_moved_offer_ids: {row.get('requested_moved_offer_ids','')}",
            f"- moved_offer_ids_on_split: {row.get('moved_offer_ids_on_split','')}",
            f"- moved_offer_ids_missing_on_split: {row.get('moved_offer_ids_missing_on_split','')}",
            f"- requested_moved_raw_offer_ids: {row.get('requested_moved_raw_offer_ids','')}",
            f"- moved_raw_offer_ids_on_split: {row.get('moved_raw_offer_ids_on_split','')}",
            f"- moved_raw_offer_ids_missing_on_split: {row.get('moved_raw_offer_ids_missing_on_split','')}",
            f"- requested_split_productprice_ids: {row.get('requested_split_productprice_ids','')}",
            f"- split_productprice_ids_on_split: {row.get('split_productprice_ids_on_split','')}",
            f"- split_productprice_ids_missing_on_split: {row.get('split_productprice_ids_missing_on_split','')}",
            f"- recommended_split_product_action: {row.get('recommended_split_product_action','')}",
            f"- safety_blockers: {row.get('safety_blockers','')}",
            f"- clean: {row.get('clean', False)}",
            f"- csv: {csv_path}",
        ]
        _write_md(md_path, title="AutoDB product split rollback dry-run", lines=lines)
        self.stdout.write("DRY_RUN_OK")
        self.stdout.write(f"csv={csv_path}")
        self.stdout.write(f"md={md_path}")
