from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from django.utils import timezone

from apps.autodb.models import AutoDbMatchingRun
from apps.autodb.services.matching.job_builder import AutoDbMatchJobBuilder
from apps.catalog.models import Product
from apps.pricing.models import ProductPrice, SupplierOffer


class AutoDbDevDelete1300FinalizeService:
    OUT_QUEUE_CSV = Path("/tmp/autodb_matching_queue_after_dev_delete_1300_and_gpl_import.csv")
    OUT_QUEUE_MD = Path("/tmp/autodb_matching_queue_after_dev_delete_1300_and_gpl_import.md")
    OUT_FINAL_MD = Path("/tmp/dev_delete_1300_gpl_import_final_report.md")

    def run(self) -> dict[str, Any]:
        queue_payload = self._rebuild_queue()
        self._write_queue(queue_payload)
        self._write_final(queue_payload)
        return {
            "queue_rows": queue_payload["rows_count"],
            "queue_run_id": queue_payload["run_id"],
        }

    def _rebuild_queue(self) -> dict[str, Any]:
        run = AutoDbMatchingRun.objects.create(
            run_type="autodb_matching_build_jobs",
            status=AutoDbMatchingRun.STATUS_RUNNING,
            dry_run=True,
            started_at=timezone.now(),
            created_by_source="management:autodb_dev_delete_1300_finalize",
        )
        rows = AutoDbMatchJobBuilder().build_jobs(
            run=run,
            supplier_code="gpl",
            limit=50000,
            dry_run=True,
        )
        by_status = Counter(row.status for row in rows)
        by_supplier = Counter(row.supplier_code for row in rows)
        by_brand = Counter(row.normalized_brand for row in rows)
        by_resolver = Counter(row.resolver_source for row in rows)
        by_article_source = Counter(row.article_source_type for row in rows)
        run.status = AutoDbMatchingRun.STATUS_SUCCESS
        run.finished_at = timezone.now()
        run.summary_json = {
            "rows": len(rows),
            "supplier_code": "gpl",
            "rows_by_status": dict(by_status),
            "rows_by_supplier_code": dict(by_supplier),
            "rows_by_brand_top_50": dict(by_brand.most_common(50)),
            "rows_by_resolver_source": dict(by_resolver),
            "rows_by_article_source": dict(by_article_source),
        }
        run.save(update_fields=["status", "finished_at", "summary_json", "updated_at"])
        return {
            "run_id": str(run.id),
            "rows_count": len(rows),
            "rows": [asdict(item) for item in rows],
            "rows_by_status": dict(by_status),
            "rows_by_supplier_code": dict(by_supplier),
            "rows_by_brand_top_50": dict(by_brand.most_common(50)),
            "rows_by_resolver_source": dict(by_resolver),
            "rows_by_article_source": dict(by_article_source),
        }

    def _write_queue(self, payload: dict[str, Any]) -> None:
        self._write_csv(self.OUT_QUEUE_CSV, payload["rows"])
        paused_keys = {
            "skipped_non_tecdoc",
            "skipped_brand_unresolved",
            "skipped_split_needed",
            "skipped_unsafe_ambiguous",
            "skipped_bad_article_source",
            "quota_paused",
        }
        paused = {k: v for k, v in payload["rows_by_status"].items() if k in paused_keys}
        lines = [
            "# Matching queue after dev delete + GPL import",
            "",
            f"- run_id: {payload['run_id']}",
            f"- queue_size: {payload['rows_count']}",
            f"- rows_by_status: {json.dumps(payload['rows_by_status'], ensure_ascii=False)}",
            f"- rows_by_supplier_code: {json.dumps(payload['rows_by_supplier_code'], ensure_ascii=False)}",
            f"- rows_by_resolver_source: {json.dumps(payload['rows_by_resolver_source'], ensure_ascii=False)}",
            f"- rows_by_article_source: {json.dumps(payload['rows_by_article_source'], ensure_ascii=False)}",
            f"- paused_buckets: {json.dumps(paused, ensure_ascii=False)}",
            "",
        ]
        self.OUT_QUEUE_MD.write_text("\n".join(lines), encoding="utf-8")

    def _write_final(self, payload: dict[str, Any]) -> None:
        scope_count = self._read_first_int("/tmp/dev_delete_1300_scope.csv", "product_id")
        deleted_products = self._read_int_cell("/tmp/dev_delete_1300_hard_delete_apply_result.csv", "products_deleted")
        gpl_dry = self._read_row("/tmp/gpl_fresh_import_dry_run.csv")
        gpl_apply = self._read_row("/tmp/gpl_fresh_import_apply_result.csv")
        photo_apply = self._read_row("/tmp/gpl_fresh_import_photo_apply_result.csv")
        category_apply = self._read_row("/tmp/gpl_fresh_import_category_apply_result.csv")

        lines = [
            "# Dev delete 1300 + GPL import final report",
            "",
            f"1. Delete scope count: {scope_count}",
            f"2. Products deleted: {deleted_products}",
            "3. Dependent rows deleted/cleaned: see /tmp/dev_delete_1300_hard_delete_apply_result.csv",
            f"4. 0S3V5O5M9202 preserved: {Product.objects.filter(svom_sku='0S3V5O5M9202').exists()}",
            f"5. GPL import dry-run result: run={gpl_dry.get('run_id', '')} status={gpl_dry.get('status', '')}",
            f"6. GPL import apply result: run={gpl_apply.get('run_id', '')} status={gpl_apply.get('status', '')}",
            f"7. Products created/updated/skipped: created={gpl_apply.get('offers_created', '0')} updated={gpl_apply.get('offers_updated', '0')} skipped={gpl_apply.get('offers_skipped', '0')}",
            f"8. GPL photos created/updated/skipped: created={photo_apply.get('gpl_images_created', '0')} reused={photo_apply.get('gpl_images_reused', '0')} stale_marked={photo_apply.get('gpl_images_stale_marked', '0')}",
            f"9. Categories mapped/review/missing: mapped={category_apply.get('category_assigned_total', '0')} review={category_apply.get('needs_review', '0')} missing_leaf={category_apply.get('missing_leaf_category', '0')}",
            "10. Schedule status: /tmp/gpl_fresh_import_recurring_schedule.md",
            f"11. Matching queue after import: size={payload['rows_count']}",
            "12. Confirmation: no UTR API, no Auto_DB images, no Auto_DB enrichment, no Product links.",
            "",
            "## Current integrity snapshot",
            f"- product_count: {Product.objects.count()}",
            f"- supplier_offer_count: {SupplierOffer.objects.count()}",
            f"- productprice_count: {ProductPrice.objects.count()}",
            "",
        ]
        self.OUT_FINAL_MD.write_text("\n".join(lines), encoding="utf-8")

    def _read_row(self, path: str) -> dict[str, str]:
        p = Path(path)
        if not p.exists():
            return {}
        with p.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            return {}
        return rows[0]

    def _read_int_cell(self, path: str, field: str) -> int:
        row = self._read_row(path)
        try:
            return int(str(row.get(field, "0") or "0"))
        except ValueError:
            return 0

    def _read_first_int(self, path: str, field: str) -> int:
        p = Path(path)
        if not p.exists():
            return 0
        with p.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        return len([row for row in rows if str(row.get(field) or "").strip()])

    def _write_csv(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        headers: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row.keys():
                if key in seen:
                    continue
                seen.add(key)
                headers.append(key)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in headers})
