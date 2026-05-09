from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.autodb.services import AutoDbRawCloneStorage, AutoDbRootGroupToSiteRootMapper
from apps.autodb.services.column_helpers import find_value


class Command(BaseCommand):
    help = "Read-only audit for PRD-level mapping to site root categories."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=5000, help="How many PRD rows to inspect.")
        parser.add_argument("--export-csv", required=True, help="CSV output path.")

    def handle(self, *args, **options):
        limit = max(int(options.get("limit") or 0), 1)
        export_csv = str(options.get("export_csv") or "").strip()
        mapper = AutoDbRootGroupToSiteRootMapper()
        storage = AutoDbRawCloneStorage()

        storage.ensure_table("prd")
        columns = list(storage.get_local_columns("prd"))
        rows = storage.fetch_local_rows(
            table="prd",
            limit=limit,
            columns=columns,
            order_by="id",
        )

        mapped_rows: list[dict[str, str]] = []
        status_counts = Counter()
        root_counts = Counter()
        reasons_needs_review = Counter()
        reasons_skipped = Counter()

        for row in rows:
            prd_id = str(find_value(row, ["id"]) or "")
            description = str(find_value(row, ["description", "Description"]) or "").strip()
            normalized = str(find_value(row, ["normalizeddescription", "NormalizedDescription"]) or "").strip()
            assembly = str(find_value(row, ["assemblygroupdescription", "AssemblyGroupDescription"]) or "").strip()
            usage = str(find_value(row, ["usagedescription", "UsageDescription"]) or "").strip()

            mapped = mapper.map_prd(
                root_group=assembly,
                prd_description=description,
                prd_normalized_description=normalized,
                prd_assembly_group_description=assembly,
                prd_usage_description=usage,
            )

            child_name = normalized or description
            mapped_rows.append(
                {
                    "prd_id": prd_id,
                    "prd.description": description,
                    "prd.normalizeddescription": normalized,
                    "prd.assemblygroupdescription": assembly,
                    "prd.usagedescription": usage,
                    "proposed_site_root": mapped.site_root_name,
                    "proposed_parent_slug": mapped.site_root_slug,
                    "proposed_child_category_name": child_name,
                    "confidence": f"{mapped.confidence:.3f}",
                    "reason": mapped.reason,
                    "status": mapped.status,
                }
            )

            status_counts[mapped.status] += 1
            if mapped.site_root_name:
                root_counts[mapped.site_root_name] += 1
            if mapped.status == mapper.STATUS_NEEDS_REVIEW:
                reasons_needs_review[mapped.reason] += 1
            if mapped.status == mapper.STATUS_SKIPPED_NO_ROOT_MAPPING:
                reasons_skipped[mapped.reason] += 1

        self._write_csv(path=export_csv, rows=mapped_rows)

        self.stdout.write("autodb_audit_prd_root_mapping summary:")
        self.stdout.write(f"- total_prd_checked: {len(mapped_rows)}")
        self.stdout.write(f"- mapped: {status_counts.get(mapper.STATUS_MAPPED, 0)}")
        self.stdout.write(f"- needs_review: {status_counts.get(mapper.STATUS_NEEDS_REVIEW, 0)}")
        self.stdout.write(f"- skipped_no_root_mapping: {status_counts.get(mapper.STATUS_SKIPPED_NO_ROOT_MAPPING, 0)}")
        self.stdout.write("- counts_by_site_root:")
        for root_name, count in sorted(root_counts.items()):
            self.stdout.write(f"  - {root_name}: {count}")
        self.stdout.write("- top_needs_review:")
        for reason, count in reasons_needs_review.most_common(10):
            self.stdout.write(f"  - {reason}: {count}")
        self.stdout.write("- top_skipped_no_root_mapping:")
        for reason, count in reasons_skipped.most_common(10):
            self.stdout.write(f"  - {reason}: {count}")
        self.stdout.write(f"- csv_export: {export_csv}")
        self.stdout.write("- report_mode: read-only")
        self.stdout.write("- UTR calls=0")

    def _write_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "prd_id",
                    "prd.description",
                    "prd.normalizeddescription",
                    "prd.assemblygroupdescription",
                    "prd.usagedescription",
                    "proposed_site_root",
                    "proposed_parent_slug",
                    "proposed_child_category_name",
                    "confidence",
                    "reason",
                    "status",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
