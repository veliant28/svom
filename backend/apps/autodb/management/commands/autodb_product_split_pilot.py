from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.matching import AutoDbProductSplitPilotService


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
    help = "Service-backed pilot split for one product SKU (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--sku", type=str, required=True)
        parser.add_argument("--moved-offer-id", action="append", dest="moved_offer_ids", default=[])
        parser.add_argument("--keep-group", type=str, default="")
        parser.add_argument("--move-group", type=str, default="")
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--apply", action="store_true", default=False)
        parser.add_argument("--export-prefix", type=str, default="/tmp/autodb_product_split_pilot")

    def handle(self, *args, **options):
        sku = str(options.get("sku") or "").strip()
        moved_offer_ids = [str(item or "").strip() for item in options.get("moved_offer_ids") or [] if str(item or "").strip()]
        keep_group = str(options.get("keep_group") or "").strip()
        move_group = str(options.get("move_group") or "").strip()
        apply_mode = bool(options.get("apply"))
        if not moved_offer_ids:
            raise CommandError("--moved-offer-id is required at least once")
        if not keep_group or not move_group:
            raise CommandError("--keep-group and --move-group are required")

        service = AutoDbProductSplitPilotService()
        prefix = Path(str(options.get("export_prefix") or "/tmp/autodb_product_split_pilot"))
        csv_path = prefix.with_suffix(".csv")
        md_path = prefix.with_suffix(".md")

        if apply_mode:
            result = service.apply(
                sku=sku,
                moved_offer_ids=moved_offer_ids,
                keep_group=keep_group,
                move_group=move_group,
            )
            row = asdict(result)
            _write_csv(csv_path, [row])
            lines = [
                "- mode: apply",
                f"- sku: {sku}",
                f"- source_product_id: {row.get('source_product_id','')}",
                f"- new_product_id: {row.get('new_product_id','')}",
                f"- moved_offer_ids: {row.get('moved_offer_ids','')}",
                f"- productprice_action: {row.get('productprice_action','')}",
                f"- rollback_fields: {row.get('rollback_fields','')}",
                f"- csv: {csv_path}",
            ]
            _write_md(md_path, title="AutoDB product split pilot apply", lines=lines)
            self.stdout.write("APPLY_OK")
            self.stdout.write(f"csv={csv_path}")
            self.stdout.write(f"md={md_path}")
            return

        plan = service.plan(
            sku=sku,
            moved_offer_ids=moved_offer_ids,
            keep_group=keep_group,
            move_group=move_group,
        )
        row = asdict(plan)
        _write_csv(csv_path, [row])
        lines = [
            "- mode: dry_run",
            f"- sku: {sku}",
            f"- source_product_id: {row.get('source_product_id','')}",
            f"- moved_offer_ids: {row.get('moved_offer_ids','')}",
            f"- proposed_new_sku: {row.get('proposed_new_sku','')}",
            f"- clean: {row.get('clean', False)}",
            f"- safety_blockers: {row.get('safety_blockers','')}",
            f"- csv: {csv_path}",
        ]
        _write_md(md_path, title="AutoDB product split pilot dry-run", lines=lines)
        self.stdout.write("DRY_RUN_OK")
        self.stdout.write(f"csv={csv_path}")
        self.stdout.write(f"md={md_path}")

