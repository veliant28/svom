from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.matching.product_split_v2 import AutoDbProductSplitV2Service


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
    help = "Split v2 pilot (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--sku", type=str, required=True)
        parser.add_argument("--source-product-id", type=str, required=True)
        parser.add_argument("--moved-offer-id", action="append", dest="moved_offer_ids", default=[])
        parser.add_argument("--moved-raw-offer-id", action="append", dest="moved_raw_offer_ids", default=[])
        parser.add_argument("--keep-group", type=str, required=True)
        parser.add_argument("--move-group", type=str, required=True)
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--apply", action="store_true", default=False)
        parser.add_argument("--export-prefix", type=str, default="/tmp/autodb_product_split_v2")

    def handle(self, *args, **options):
        sku = str(options.get("sku") or "").strip()
        source_product_id = str(options.get("source_product_id") or "").strip()
        moved_offer_ids = [str(item or "").strip() for item in options.get("moved_offer_ids") or [] if str(item or "").strip()]
        moved_raw_offer_ids = [str(item or "").strip() for item in options.get("moved_raw_offer_ids") or [] if str(item or "").strip()]
        keep_group = str(options.get("keep_group") or "").strip()
        move_group = str(options.get("move_group") or "").strip()
        apply_mode = bool(options.get("apply"))

        if not moved_offer_ids:
            raise CommandError("--moved-offer-id is required at least once")
        if apply_mode and not moved_raw_offer_ids:
            raise CommandError("--moved-raw-offer-id is required at least once for --apply")

        service = AutoDbProductSplitV2Service()
        prefix = Path(str(options.get("export_prefix") or "/tmp/autodb_product_split_v2"))
        csv_path = prefix.with_suffix(".csv")
        md_path = prefix.with_suffix(".md")

        if apply_mode:
            result = service.apply(
                sku=sku,
                source_product_id=source_product_id,
                moved_offer_ids=moved_offer_ids,
                moved_raw_offer_ids=moved_raw_offer_ids,
                keep_group=keep_group,
                move_group=move_group,
            )
            row = asdict(result)
            _write_csv(csv_path, [row])
            lines = [
                "- mode: apply",
                f"- source_product_id: {row.get('source_product_id','')}",
                f"- new_product_id: {row.get('new_product_id','')}",
                f"- new_product_sku: {row.get('new_product_sku','')}",
                f"- new_product_svom_sku: {row.get('new_product_svom_sku','')}",
                f"- moved_offer_ids: {row.get('moved_offer_ids','')}",
                f"- moved_raw_offer_ids: {row.get('moved_raw_offer_ids','')}",
                f"- source_productprice_ids: {row.get('source_productprice_ids','')}",
                f"- new_productprice_id: {row.get('new_productprice_id','')}",
                f"- csv: {csv_path}",
            ]
            _write_md(md_path, title="Split v2 apply", lines=lines)
            self.stdout.write("APPLY_OK")
            self.stdout.write(f"csv={csv_path}")
            self.stdout.write(f"md={md_path}")
            return

        plan = service.plan(
            sku=sku,
            source_product_id=source_product_id,
            moved_offer_ids=moved_offer_ids,
            keep_group=keep_group,
            move_group=move_group,
        )
        row = asdict(plan)
        _write_csv(csv_path, [row])
        lines = [
            "- mode: dry_run",
            f"- source_product_id: {row.get('source_product_id','')}",
            f"- clean: {row.get('clean', False)}",
            f"- blockers: {row.get('blockers','')}",
            f"- proposed_internal_sku: {row.get('proposed_internal_sku','')}",
            f"- proposed_public_sku_strategy: {row.get('proposed_public_sku_strategy','')}",
            f"- offers_to_move: {row.get('offers_to_move','')}",
            f"- raw_offers_to_move: {row.get('raw_offers_to_move','')}",
            f"- productprice_actions: {row.get('productprice_actions','')}",
            f"- csv: {csv_path}",
        ]
        _write_md(md_path, title="Split v2 dry-run", lines=lines)
        self.stdout.write("DRY_RUN_OK")
        self.stdout.write(f"csv={csv_path}")
        self.stdout.write(f"md={md_path}")
