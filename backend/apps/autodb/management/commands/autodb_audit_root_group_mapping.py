from __future__ import annotations

import csv
import os
from collections import Counter
from pathlib import Path

import pymysql
from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services import AutoDbRootGroupToSiteRootMapper


class Command(BaseCommand):
    help = "Read-only audit of Auto_DB_Pro root groups mapped to site root categories."

    def add_arguments(self, parser):
        parser.add_argument("--export-csv", required=True, help="CSV output path.")

    def handle(self, *args, **options):
        export_csv = str(options["export_csv"]).strip()
        if not export_csv:
            raise CommandError("--export-csv is required")

        host = os.environ.get("AUTODB_PRO_REMOTE_HOST") or os.environ.get("AUTODB_SOURCE_MYSQL_HOST")
        user = os.environ.get("AUTODB_PRO_REMOTE_USER") or os.environ.get("AUTODB_SOURCE_MYSQL_USER")
        password = os.environ.get("AUTODB_PRO_REMOTE_PASSWORD") or os.environ.get("AUTODB_SOURCE_MYSQL_PASSWORD")
        database = os.environ.get("AUTODB_PRO_REMOTE_DATABASE") or os.environ.get("AUTODB_SOURCE_MYSQL_DATABASE")
        if not host or not user or not password or not database:
            raise CommandError("Remote Auto_DB_Pro credentials are missing in environment.")

        mapper = AutoDbRootGroupToSiteRootMapper()
        rows = self._read_remote_rows(host=host, user=user, password=password, database=database)
        mapped_rows: list[dict] = []
        counts_by_site_root = Counter()
        status_counts = Counter()
        for row in rows:
            group_name = str(row.get("group_name") or "").strip()
            root_count = int(row.get("root_rows_count") or 0)
            sample_text = str(row.get("sample_text") or "")
            mapped = mapper.map_group(root_group=group_name, sample_text=sample_text)
            mapped_rows.append(
                {
                    "autodb_root_group": group_name,
                    "root_rows_count": root_count,
                    "sample_text": sample_text,
                    "proposed_site_root_slug": mapped.site_root_slug,
                    "proposed_site_root_name": mapped.site_root_name,
                    "confidence": f"{mapped.confidence:.3f}",
                    "reason": mapped.reason,
                    "status": mapped.status,
                }
            )
            status_counts[mapped.status] += 1
            if mapped.site_root_name:
                counts_by_site_root[mapped.site_root_name] += 1

        self._write_csv(export_csv=export_csv, rows=mapped_rows)
        self.stdout.write("autodb_audit_root_group_mapping summary:")
        self.stdout.write(f"- remote_host: {host}")
        self.stdout.write(f"- remote_database: {database}")
        self.stdout.write(f"- total_autodb_root_groups: {len(mapped_rows)}")
        self.stdout.write(f"- mapped: {status_counts.get(mapper.STATUS_MAPPED, 0)}")
        self.stdout.write(f"- needs_review: {status_counts.get(mapper.STATUS_NEEDS_REVIEW, 0)}")
        self.stdout.write(
            f"- skipped_no_root_mapping: {status_counts.get(mapper.STATUS_SKIPPED_NO_ROOT_MAPPING, 0)}"
        )
        self.stdout.write("- counts_by_site_root:")
        for root_name, count in sorted(counts_by_site_root.items()):
            self.stdout.write(f"  - {root_name}: {count}")
        self.stdout.write("- all_root_groups:")
        for row in mapped_rows:
            self.stdout.write(
                f"  - {row['autodb_root_group']} => {row['proposed_site_root_name'] or '-'} "
                f"[{row['status']}] confidence={row['confidence']} reason={row['reason']}"
            )
        self.stdout.write(f"- csv_export: {export_csv}")
        self.stdout.write("- report_mode: read-only")
        self.stdout.write("- UTR calls=0")

    def _read_remote_rows(self, *, host: str, user: str, password: str, database: str) -> list[dict]:
        connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=20,
            read_timeout=120,
            write_timeout=120,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        roots.description AS group_name,
                        roots.root_rows_count,
                        COALESCE(samples.sample_text, '') AS sample_text
                    FROM (
                        SELECT description, COUNT(*) AS root_rows_count
                        FROM passanger_car_trees
                        WHERE parentid IS NULL OR parentid = 0
                        GROUP BY description
                    ) roots
                    LEFT JOIN (
                        SELECT
                            p.assemblygroupdescription AS description,
                            MIN(CONCAT_WS(' | ', p.description, p.normalizeddescription, p.usagedescription)) AS sample_text
                        FROM prd p
                        WHERE p.assemblygroupdescription IS NOT NULL AND p.assemblygroupdescription <> ''
                        GROUP BY p.assemblygroupdescription
                    ) samples ON samples.description = roots.description
                    ORDER BY roots.description
                    """
                )
                return list(cursor.fetchall())
        finally:
            connection.close()

    def _write_csv(self, *, export_csv: str, rows: list[dict]) -> None:
        path = Path(export_csv).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "autodb_root_group",
                    "root_rows_count",
                    "sample_text",
                    "proposed_site_root_slug",
                    "proposed_site_root_name",
                    "confidence",
                    "reason",
                    "status",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
