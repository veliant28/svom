from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.matching.product_split_artifact_cleanup import AutoDbSplitArtifactCleanupService


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
    help = "Cleanup orphan inactive split product artifact (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--product-id", type=str, required=True)
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--apply", action="store_true", default=False)
        parser.add_argument("--export-prefix", type=str, default="/tmp/autodb_product_split_artifact_cleanup")

    def handle(self, *args, **options):
        product_id = str(options.get("product_id") or "").strip()
        if not product_id:
            raise CommandError("--product-id is required")
        apply_mode = bool(options.get("apply"))

        service = AutoDbSplitArtifactCleanupService()
        prefix = Path(str(options.get("export_prefix") or "/tmp/autodb_product_split_artifact_cleanup"))
        csv_path = prefix.with_suffix(".csv")
        md_path = prefix.with_suffix(".md")

        if apply_mode:
            result = service.apply(product_id=product_id)
            row = asdict(result)
            _write_csv(csv_path, [row])
            lines = [
                "- mode: apply",
                f"- product_id: {row.get('product_id','')}",
                f"- action: {row.get('action','')}",
                f"- deleted: {row.get('deleted', False)}",
                f"- ignored_marker_applied: {row.get('ignored_marker_applied', False)}",
                f"- service_job_id: {row.get('service_job_id','')}",
                f"- service_evidence_id: {row.get('service_evidence_id','')}",
                f"- csv: {csv_path}",
            ]
            _write_md(md_path, title="Split artifact cleanup apply", lines=lines)
            self.stdout.write("APPLY_OK")
            self.stdout.write(f"csv={csv_path}")
            self.stdout.write(f"md={md_path}")
            return

        plan = service.plan(product_id=product_id)
        row = asdict(plan)
        _write_csv(csv_path, [row])
        lines = [
            "- mode: dry_run",
            f"- product_id: {row.get('product_id','')}",
            f"- exists: {row.get('exists', False)}",
            f"- sku: {row.get('sku','')}",
            f"- is_active: {row.get('is_active', False)}",
            f"- would_delete_product: {row.get('would_delete_product', False)}",
            f"- would_keep_inactive_and_ignore: {row.get('would_keep_inactive_and_ignore', False)}",
            f"- dependency_rows: {row.get('dependency_rows','')}",
            f"- safety_blockers: {row.get('safety_blockers','')}",
            f"- clean: {row.get('clean', False)}",
            f"- csv: {csv_path}",
        ]
        _write_md(md_path, title="Split artifact cleanup dry-run", lines=lines)
        self.stdout.write("DRY_RUN_OK")
        self.stdout.write(f"csv={csv_path}")
        self.stdout.write(f"md={md_path}")
