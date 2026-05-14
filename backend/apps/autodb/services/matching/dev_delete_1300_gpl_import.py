from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob, AutoDbMatchingRun
from apps.autodb.services.matching.job_builder import AutoDbMatchJobBuilder
from apps.catalog.models import AutoDbProductLinkQuality, Product, ProductAttribute, ProductImage
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import ImportRowError, ImportRun, SupplierPriceList
from apps.supplier_imports.selectors import ensure_default_import_sources, get_import_source_by_code
from apps.supplier_imports.services import SupplierImportRunner
from apps.supplier_imports.models import SupplierRawOffer


class AutoDbDevDelete1300AndFreshGplImportService:
    OUTPUT_SCOPE_CSV = Path("/tmp/dev_delete_1300_scope.csv")
    OUTPUT_SCOPE_MD = Path("/tmp/dev_delete_1300_scope.md")

    OUTPUT_BACKUP_PRODUCTS = Path("/tmp/dev_delete_1300_backup_products.csv")
    OUTPUT_BACKUP_SO = Path("/tmp/dev_delete_1300_backup_supplier_offers.csv")
    OUTPUT_BACKUP_SRO = Path("/tmp/dev_delete_1300_backup_supplier_raw_offers.csv")
    OUTPUT_BACKUP_PP = Path("/tmp/dev_delete_1300_backup_product_prices.csv")
    OUTPUT_BACKUP_PI = Path("/tmp/dev_delete_1300_backup_product_images.csv")
    OUTPUT_BACKUP_PA = Path("/tmp/dev_delete_1300_backup_product_attributes.csv")
    OUTPUT_BACKUP_PF = Path("/tmp/dev_delete_1300_backup_product_fitments.csv")
    OUTPUT_BACKUP_MATCH = Path("/tmp/dev_delete_1300_backup_matching_state.csv")
    OUTPUT_BACKUP_MANIFEST = Path("/tmp/dev_delete_1300_backup_manifest.md")

    OUTPUT_DRY_CSV = Path("/tmp/dev_delete_1300_hard_delete_dry_run.csv")
    OUTPUT_DRY_MD = Path("/tmp/dev_delete_1300_hard_delete_dry_run.md")
    OUTPUT_APPLY_CSV = Path("/tmp/dev_delete_1300_hard_delete_apply_result.csv")
    OUTPUT_APPLY_MD = Path("/tmp/dev_delete_1300_hard_delete_apply_result.md")
    OUTPUT_VERIFY_CSV = Path("/tmp/dev_delete_1300_hard_delete_verification.csv")
    OUTPUT_VERIFY_MD = Path("/tmp/dev_delete_1300_hard_delete_verification.md")

    OUTPUT_GPL_PLAN = Path("/tmp/gpl_fresh_import_plan.md")
    OUTPUT_GPL_PHOTO_POLICY = Path("/tmp/gpl_fresh_import_photo_policy.md")
    OUTPUT_GPL_CATEGORY_POLICY = Path("/tmp/gpl_fresh_import_category_policy.md")
    OUTPUT_GPL_DRY_CSV = Path("/tmp/gpl_fresh_import_dry_run.csv")
    OUTPUT_GPL_DRY_MD = Path("/tmp/gpl_fresh_import_dry_run.md")
    OUTPUT_GPL_PHOTO_DRY_CSV = Path("/tmp/gpl_fresh_import_photo_dry_run.csv")
    OUTPUT_GPL_CATEGORY_DRY_CSV = Path("/tmp/gpl_fresh_import_category_dry_run.csv")
    OUTPUT_GPL_CONFLICTS_CSV = Path("/tmp/gpl_fresh_import_conflicts.csv")
    OUTPUT_GPL_APPLY_CSV = Path("/tmp/gpl_fresh_import_apply_result.csv")
    OUTPUT_GPL_APPLY_MD = Path("/tmp/gpl_fresh_import_apply_result.md")
    OUTPUT_GPL_PHOTO_APPLY_CSV = Path("/tmp/gpl_fresh_import_photo_apply_result.csv")
    OUTPUT_GPL_CATEGORY_APPLY_CSV = Path("/tmp/gpl_fresh_import_category_apply_result.csv")
    OUTPUT_GPL_SCHEDULE_MD = Path("/tmp/gpl_fresh_import_recurring_schedule.md")

    OUTPUT_QUEUE_CSV = Path("/tmp/autodb_matching_queue_after_dev_delete_1300_and_gpl_import.csv")
    OUTPUT_QUEUE_MD = Path("/tmp/autodb_matching_queue_after_dev_delete_1300_and_gpl_import.md")
    OUTPUT_FINAL_MD = Path("/tmp/dev_delete_1300_gpl_import_final_report.md")

    QUARANTINE_STATUSES = {
        "skipped_split_product_candidate",
        "skipped_multi_offer_conflict",
        "needs_review",
        "needs_review_trusted_conflict",
    }
    PRESERVE_SVOM_SKUS = {"0S3V5O5M9202", "8S2V7O1M9900"}
    PRESERVE_INTERNAL_SKUS = {"FE01111"}
    RELEASED_REASON = "quarantine_released_by_split_v2"

    def run(self) -> dict[str, Any]:
        ensure_default_import_sources()
        global_before = self._global_snapshot()

        preserved_ids = self._load_preserved_product_ids()
        scope_rows = self._build_delete_scope_rows(preserved_ids=preserved_ids)
        self._write_csv(self.OUTPUT_SCOPE_CSV, scope_rows)
        self._write_md(
            self.OUTPUT_SCOPE_MD,
            title="Dev delete 1300 scope",
            lines=[
                f"- scoped_products: {len(scope_rows)}",
                f"- preserved_products: {len(preserved_ids)}",
                f"- quarantine_statuses: {', '.join(sorted(self.QUARANTINE_STATUSES))}",
            ],
        )

        scope_ids = [str(row["product_id"]) for row in scope_rows]
        self._export_backups(scope_ids=scope_ids)
        dry_run = self._build_delete_dry_run(scope_ids=scope_ids, preserved_ids=preserved_ids)
        self._write_csv(self.OUTPUT_DRY_CSV, [dry_run])
        self._write_md(
            self.OUTPUT_DRY_MD,
            title="Dev hard delete dry-run",
            lines=[
                f"- products_to_delete: {dry_run['products_to_delete']}",
                f"- supplier_offers_to_delete: {dry_run['supplier_offers_to_delete']}",
                f"- supplier_raw_offers_to_delete: {dry_run['supplier_raw_offers_to_delete']}",
                f"- product_prices_to_delete: {dry_run['product_prices_to_delete']}",
                f"- product_images_to_delete: {dry_run['product_images_to_delete']}",
                f"- product_attributes_to_delete: {dry_run['product_attributes_to_delete']}",
                f"- product_fitments_to_delete: {dry_run['product_fitments_to_delete']}",
                f"- matching_jobs_to_delete: {dry_run['matching_jobs_to_delete']}",
                f"- matching_evidence_to_delete: {dry_run['matching_evidence_to_delete']}",
                f"- protected_0S3V5O5M9202_excluded: {dry_run['preserved_main_excluded']}",
                f"- protected_split_pair_excluded: {dry_run['preserved_split_excluded']}",
            ],
        )

        apply_result = self._apply_hard_delete(scope_ids=scope_ids)
        self._write_csv(self.OUTPUT_APPLY_CSV, [apply_result])
        self._write_md(
            self.OUTPUT_APPLY_MD,
            title="Dev hard delete apply result",
            lines=[
                f"- products_deleted: {apply_result['products_deleted']}",
                f"- supplier_offers_deleted: {apply_result['supplier_offers_deleted']}",
                f"- supplier_raw_offers_deleted: {apply_result['supplier_raw_offers_deleted']}",
                f"- product_prices_deleted: {apply_result['product_prices_deleted']}",
                f"- product_images_deleted: {apply_result['product_images_deleted']}",
                f"- product_attributes_deleted: {apply_result['product_attributes_deleted']}",
                f"- product_fitments_deleted: {apply_result['product_fitments_deleted']}",
                f"- matching_jobs_deleted: {apply_result['matching_jobs_deleted']}",
                f"- matching_evidence_deleted: {apply_result['matching_evidence_deleted']}",
            ],
        )

        verification = self._verify_delete(scope_ids=scope_ids, preserved_ids=preserved_ids)
        self._write_csv(self.OUTPUT_VERIFY_CSV, [verification])
        self._write_md(
            self.OUTPUT_VERIFY_MD,
            title="Dev hard delete verification",
            lines=[
                f"- deleted_products_remaining: {verification['deleted_products_remaining']}",
                f"- preserved_products_existing: {verification['preserved_products_existing']}",
                f"- orphan_supplier_offers_for_scope: {verification['orphan_supplier_offers_for_scope']}",
                f"- orphan_product_prices_for_scope: {verification['orphan_product_prices_for_scope']}",
                f"- orphan_product_images_for_scope: {verification['orphan_product_images_for_scope']}",
                f"- queue_rows_for_deleted_products: {verification['queue_rows_for_deleted_products']}",
            ],
        )

        latest_file = self._latest_gpl_download_path()
        self._write_gpl_policies(latest_file=latest_file)

        gpl_dry = self._run_gpl_import(dry_run=True, latest_file=latest_file)
        self._export_gpl_result(
            result=gpl_dry,
            summary_csv=self.OUTPUT_GPL_DRY_CSV,
            summary_md=self.OUTPUT_GPL_DRY_MD,
            photo_csv=self.OUTPUT_GPL_PHOTO_DRY_CSV,
            category_csv=self.OUTPUT_GPL_CATEGORY_DRY_CSV,
            conflicts_csv=self.OUTPUT_GPL_CONFLICTS_CSV,
        )

        gpl_apply = self._run_gpl_import(dry_run=False, latest_file=latest_file)
        self._export_gpl_result(
            result=gpl_apply,
            summary_csv=self.OUTPUT_GPL_APPLY_CSV,
            summary_md=self.OUTPUT_GPL_APPLY_MD,
            photo_csv=self.OUTPUT_GPL_PHOTO_APPLY_CSV,
            category_csv=self.OUTPUT_GPL_CATEGORY_APPLY_CSV,
            conflicts_csv=None,
        )

        self._write_gpl_schedule()
        queue_payload = self._rebuild_matching_queue()
        self._write_queue_payload(queue_payload)

        global_after = self._global_snapshot()
        self._write_final_report(
            scope_count=len(scope_rows),
            delete_result=apply_result,
            gpl_dry=gpl_dry,
            gpl_apply=gpl_apply,
            queue_payload=queue_payload,
            global_before=global_before,
            global_after=global_after,
        )
        return {
            "scope_count": len(scope_rows),
            "delete_products": apply_result["products_deleted"],
            "gpl_dry_run_id": gpl_dry["run_id"],
            "gpl_apply_run_id": gpl_apply["run_id"],
            "queue_rows": queue_payload["rows_count"],
        }

    def _load_preserved_product_ids(self) -> set[str]:
        ids = set(
            Product.objects.filter(
                Q(svom_sku__in=self.PRESERVE_SVOM_SKUS) | Q(sku__in=self.PRESERVE_INTERNAL_SKUS)
            ).values_list("id", flat=True)
        )
        pilots_csv = Path("/tmp/product_quality_split_v2_two_pilots_state_verification.csv")
        if pilots_csv.exists():
            with pilots_csv.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    if str(row.get("pilot") or "").strip() != "1":
                        continue
                    ids.add(str(row.get("product_id") or "").strip())
        return {pid for pid in ids if pid}

    def _build_delete_scope_rows(self, *, preserved_ids: set[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        q = (
            Q(status__in={"skipped_split_product_candidate", "skipped_multi_offer_conflict", "needs_review_trusted_conflict"})
            | Q(status="needs_review", last_error__in={"multi_offer_guard_review", "needs_review", "needs_review_trusted_conflict"})
        )
        jobs = (
            AutoDbMatchJob.objects.select_related("product")
            .filter(q)
            .exclude(last_error=self.RELEASED_REASON)
            .order_by("product_id", "-updated_at", "-created_at")
        )
        by_product: dict[str, AutoDbMatchJob] = {}
        for job in jobs.iterator(chunk_size=5000):
            pid = str(job.product_id)
            if pid in preserved_ids:
                continue
            if pid not in by_product:
                by_product[pid] = job
        for pid in sorted(by_product.keys()):
            job = by_product[pid]
            product = job.product
            quarantine_status = str(job.status or "")
            if quarantine_status == "needs_review":
                if str(job.last_error or "").strip() == "needs_review_trusted_conflict":
                    quarantine_status = "needs_review_trusted_conflict"
                else:
                    quarantine_status = "needs_review"
            rows.append(
                {
                    "product_id": pid,
                    "sku": str(product.sku or ""),
                    "svom_sku": str(product.svom_sku or ""),
                    "product_name": str(product.name or ""),
                    "quarantine_status": quarantine_status,
                    "quarantine_reason": str(job.last_error or ""),
                    "job_id": str(job.id),
                }
            )
        return rows

    def _export_backups(self, *, scope_ids: list[str]) -> None:
        self._write_model_rows_csv(
            self.OUTPUT_BACKUP_PRODUCTS,
            Product.objects.filter(id__in=scope_ids),
        )
        self._write_model_rows_csv(
            self.OUTPUT_BACKUP_SO,
            SupplierOffer.objects.filter(product_id__in=scope_ids),
        )
        self._write_model_rows_csv(
            self.OUTPUT_BACKUP_SRO,
            SupplierRawOffer.objects.filter(matched_product_id__in=scope_ids),
        )
        self._write_model_rows_csv(
            self.OUTPUT_BACKUP_PP,
            ProductPrice.objects.filter(product_id__in=scope_ids),
        )
        self._write_model_rows_csv(
            self.OUTPUT_BACKUP_PI,
            ProductImage.objects.filter(product_id__in=scope_ids),
        )
        self._write_model_rows_csv(
            self.OUTPUT_BACKUP_PA,
            ProductAttribute.objects.filter(product_id__in=scope_ids),
        )
        self._write_model_rows_csv(
            self.OUTPUT_BACKUP_PF,
            ProductFitment.objects.filter(product_id__in=scope_ids),
        )

        jobs = list(AutoDbMatchJob.objects.filter(product_id__in=scope_ids).values())
        job_ids = [row["id"] for row in jobs]
        evidence = list(AutoDbMatchEvidence.objects.filter(job_id__in=job_ids).values()) if job_ids else []
        quality = list(AutoDbProductLinkQuality.objects.filter(product_id__in=scope_ids).values())
        state_rows: list[dict[str, Any]] = []
        for row in jobs:
            state_rows.append({"row_type": "autodb_match_job", **self._jsonify_values(row)})
        for row in evidence:
            state_rows.append({"row_type": "autodb_match_evidence", **self._jsonify_values(row)})
        for row in quality:
            state_rows.append({"row_type": "autodb_link_quality", **self._jsonify_values(row)})
        self._write_csv(self.OUTPUT_BACKUP_MATCH, state_rows)

        self._write_md(
            self.OUTPUT_BACKUP_MANIFEST,
            title="Dev delete 1300 backup manifest",
            lines=[
                f"- products: {Product.objects.filter(id__in=scope_ids).count()}",
                f"- supplier_offers: {SupplierOffer.objects.filter(product_id__in=scope_ids).count()}",
                f"- supplier_raw_offers: {SupplierRawOffer.objects.filter(matched_product_id__in=scope_ids).count()}",
                f"- product_prices: {ProductPrice.objects.filter(product_id__in=scope_ids).count()}",
                f"- product_images: {ProductImage.objects.filter(product_id__in=scope_ids).count()}",
                f"- product_attributes: {ProductAttribute.objects.filter(product_id__in=scope_ids).count()}",
                f"- product_fitments: {ProductFitment.objects.filter(product_id__in=scope_ids).count()}",
                f"- matching_state_rows: {len(state_rows)}",
            ],
        )

    def _build_delete_dry_run(self, *, scope_ids: list[str], preserved_ids: set[str]) -> dict[str, Any]:
        main_exists = Product.objects.filter(svom_sku="0S3V5O5M9202", id__in=scope_ids).exists()
        split_exists = Product.objects.filter(Q(svom_sku="8S2V7O1M9900") | Q(sku="FE01111"), id__in=scope_ids).exists()
        job_ids = list(AutoDbMatchJob.objects.filter(product_id__in=scope_ids).values_list("id", flat=True))
        return {
            "products_to_delete": Product.objects.filter(id__in=scope_ids).count(),
            "supplier_offers_to_delete": SupplierOffer.objects.filter(product_id__in=scope_ids).count(),
            "supplier_raw_offers_to_delete": SupplierRawOffer.objects.filter(matched_product_id__in=scope_ids).count(),
            "product_prices_to_delete": ProductPrice.objects.filter(product_id__in=scope_ids).count(),
            "product_images_to_delete": ProductImage.objects.filter(product_id__in=scope_ids).count(),
            "product_attributes_to_delete": ProductAttribute.objects.filter(product_id__in=scope_ids).count(),
            "product_fitments_to_delete": ProductFitment.objects.filter(product_id__in=scope_ids).count(),
            "matching_jobs_to_delete": len(job_ids),
            "matching_evidence_to_delete": AutoDbMatchEvidence.objects.filter(job_id__in=job_ids).count() if job_ids else 0,
            "preserved_products_total": len(preserved_ids),
            "preserved_main_excluded": not main_exists,
            "preserved_split_excluded": not split_exists,
        }

    def _apply_hard_delete(self, *, scope_ids: list[str]) -> dict[str, Any]:
        with transaction.atomic():
            job_ids = list(AutoDbMatchJob.objects.filter(product_id__in=scope_ids).values_list("id", flat=True))
            evidence_deleted = 0
            if job_ids:
                evidence_deleted = AutoDbMatchEvidence.objects.filter(job_id__in=job_ids).delete()[0]
            jobs_deleted = AutoDbMatchJob.objects.filter(product_id__in=scope_ids).delete()[0]
            raw_deleted = SupplierRawOffer.objects.filter(matched_product_id__in=scope_ids).delete()[0]
            quality_deleted = AutoDbProductLinkQuality.objects.filter(product_id__in=scope_ids).delete()[0]
            products_deleted = Product.objects.filter(id__in=scope_ids).delete()[0]

        return {
            "products_deleted": products_deleted,
            "supplier_offers_deleted": 0,
            "supplier_raw_offers_deleted": raw_deleted,
            "product_prices_deleted": 0,
            "product_images_deleted": 0,
            "product_attributes_deleted": 0,
            "product_fitments_deleted": 0,
            "matching_jobs_deleted": jobs_deleted,
            "matching_evidence_deleted": evidence_deleted,
            "link_quality_deleted": quality_deleted,
        }

    def _verify_delete(self, *, scope_ids: list[str], preserved_ids: set[str]) -> dict[str, Any]:
        return {
            "deleted_products_remaining": Product.objects.filter(id__in=scope_ids).count(),
            "preserved_products_existing": Product.objects.filter(id__in=preserved_ids).count(),
            "orphan_supplier_offers_for_scope": SupplierOffer.objects.filter(product_id__in=scope_ids).count(),
            "orphan_product_prices_for_scope": ProductPrice.objects.filter(product_id__in=scope_ids).count(),
            "orphan_product_images_for_scope": ProductImage.objects.filter(product_id__in=scope_ids).count(),
            "orphan_product_attributes_for_scope": ProductAttribute.objects.filter(product_id__in=scope_ids).count(),
            "orphan_product_fitments_for_scope": ProductFitment.objects.filter(product_id__in=scope_ids).count(),
            "orphan_matching_jobs_for_scope": AutoDbMatchJob.objects.filter(product_id__in=scope_ids).count(),
            "queue_rows_for_deleted_products": AutoDbMatchJob.objects.filter(product_id__in=scope_ids).count(),
            "preserved_main_exists": Product.objects.filter(svom_sku="0S3V5O5M9202").exists(),
        }

    def _latest_gpl_download_path(self) -> str:
        row = (
            SupplierPriceList.objects.filter(source__code="gpl")
            .exclude(downloaded_file_path="")
            .order_by("-downloaded_at", "-created_at")
            .first()
        )
        return str(getattr(row, "downloaded_file_path", "") or "")

    def _write_gpl_policies(self, *, latest_file: str) -> None:
        self._write_md(
            self.OUTPUT_GPL_PLAN,
            title="GPL fresh import plan",
            lines=[
                "- source: gpl",
                f"- latest_downloaded_file: {latest_file or '<default source path>'}",
                "- mode: current_offers persistence via SupplierImportRunner",
                "- autodb_enrich: disabled",
                "- autodb_remote_lookup: disabled",
                "- update_product_names: disabled",
                "- update_product_images: enabled (GPL/import only)",
            ],
        )
        self._write_md(
            self.OUTPUT_GPL_PHOTO_POLICY,
            title="GPL photo policy",
            lines=[
                "- allow ProductImage updates from GPL import payload/source",
                "- block Auto_DB image enrichment (autodb_enrich disabled)",
                "- no UTR image calls",
            ],
        )
        self._write_md(
            self.OUTPUT_GPL_CATEGORY_POLICY,
            title="GPL category policy",
            lines=[
                "- category assignment from GPL row/group mapping pipeline",
                "- unresolved/missing targets stay in needs_review buckets",
                "- no manual overwrite in this automated run",
            ],
        )

    def _run_gpl_import(self, *, dry_run: bool, latest_file: str) -> dict[str, Any]:
        source = get_import_source_by_code("gpl")
        runner = SupplierImportRunner()
        file_paths = [latest_file] if latest_file else None
        result = runner.run_source(
            source=source,
            trigger="command:autodb_dev_delete_1300_and_fresh_gpl_import",
            dry_run=dry_run,
            file_paths=file_paths,
            reprice=False,
            reindex=False,
            autodb_enrich=False,
            update_product_names=False,
            update_product_images=True,
            autodb_limit=0,
            autodb_allow_remote=False,
            row_limit=0,
        )
        run = ImportRun.objects.get(id=result.run_id)
        return {
            "run_id": str(result.run_id),
            "status": str(result.status or ""),
            "summary": run.summary or {},
            "offers_created": int(result.summary.get("offers_created", 0)),
            "offers_updated": int(result.summary.get("offers_updated", 0)),
            "offers_skipped": int(result.summary.get("offers_skipped", 0)),
            "processed_rows": int(result.summary.get("processed_rows", 0)),
            "parsed_rows": int(result.summary.get("parsed_rows", 0)),
            "errors_count": int(result.summary.get("errors_count", 0)),
            "dry_run": bool(dry_run),
        }

    def _export_gpl_result(
        self,
        *,
        result: dict[str, Any],
        summary_csv: Path,
        summary_md: Path,
        photo_csv: Path,
        category_csv: Path,
        conflicts_csv: Path | None,
    ) -> None:
        summary = result.get("summary") or {}
        summary_row = {
            "run_id": result["run_id"],
            "status": result["status"],
            "dry_run": result["dry_run"],
            "processed_rows": result["processed_rows"],
            "parsed_rows": result["parsed_rows"],
            "offers_created": result["offers_created"],
            "offers_updated": result["offers_updated"],
            "offers_skipped": result["offers_skipped"],
            "errors_count": result["errors_count"],
            "affected_products": int(summary.get("affected_products", 0)),
            "files_processed": int(summary.get("files_processed", 0)),
            "persistence_mode": str(summary.get("persistence_mode", "")),
        }
        self._write_csv(summary_csv, [summary_row])
        self._write_md(
            summary_md,
            title="GPL fresh import result",
            lines=[
                f"- run_id: {result['run_id']}",
                f"- status: {result['status']}",
                f"- dry_run: {result['dry_run']}",
                f"- offers_created: {summary_row['offers_created']}",
                f"- offers_updated: {summary_row['offers_updated']}",
                f"- offers_skipped: {summary_row['offers_skipped']}",
                f"- errors_count: {summary_row['errors_count']}",
            ],
        )

        image_info = summary.get("gpl_image_sync") or {}
        self._write_csv(
            photo_csv,
            [
                {
                    "run_id": result["run_id"],
                    "dry_run": result["dry_run"],
                    "gpl_images_created": int(image_info.get("created", 0)),
                    "gpl_images_reused": int(image_info.get("reused", 0)),
                    "gpl_images_stale_marked": int(image_info.get("stale_marked", 0)),
                    "products_with_image_updates": int(image_info.get("products_updated", 0)),
                }
            ],
        )

        category_counts = summary.get("category_status_counts") or {}
        cat_policy = summary.get("gpl_category_assignment") or {}
        self._write_csv(
            category_csv,
            [
                {
                    "run_id": result["run_id"],
                    "dry_run": result["dry_run"],
                    "auto_mapped": int(category_counts.get("auto_mapped", 0)),
                    "needs_review": int(category_counts.get("needs_review", 0)),
                    "category_assigned_total": int(cat_policy.get("category_assigned_total", 0)),
                    "category_null_total": int(cat_policy.get("category_null_total", 0)),
                    "missing_leaf_category": int(cat_policy.get("missing_leaf_category", 0)),
                    "conflict": int(cat_policy.get("conflict", 0)),
                }
            ],
        )

        if conflicts_csv is not None:
            rows = list(
                ImportRowError.objects.filter(run_id=result["run_id"])
                .values("id", "row_number", "external_sku", "error_code", "message")
                .order_by("row_number", "id")
            )
            self._write_csv(conflicts_csv, rows)

    def _write_gpl_schedule(self) -> None:
        self._write_md(
            self.OUTPUT_GPL_SCHEDULE_MD,
            title="GPL recurring import schedule",
            lines=[
                "- command: python manage.py import_supplier_data --source gpl --no-autodb-enrich --autodb-no-remote --update-product-images --no-update-product-names --no-reprice",
                "- schedule: every 6 hours (example cron: 15 */6 * * *)",
                "- source/input: latest downloaded GPL price list from supplier workspace",
                "- logs: django ImportRun summary + row errors + management command stdout",
                "- photo policy: GPL image sync only; Auto_DB images disabled",
                "- category policy: GPL mapping + needs_review bucket for unresolved categories",
                "- failure handling: keep last successful run, alert on ImportRun.status=failed or high row_errors",
            ],
        )

    def _rebuild_matching_queue(self) -> dict[str, Any]:
        run = AutoDbMatchingRun.objects.create(
            run_type="autodb_matching_build_jobs",
            status=AutoDbMatchingRun.STATUS_RUNNING,
            dry_run=False,
            started_at=timezone.now(),
            created_by_source="management:autodb_dev_delete_1300_and_fresh_gpl_import",
        )
        rows = AutoDbMatchJobBuilder().build_jobs(
            run=run,
            supplier_code="gpl",
            limit=50000,
            dry_run=False,
        )
        by_status = Counter(row.status for row in rows)
        by_resolver = Counter(row.resolver_source for row in rows)
        by_article_source = Counter(row.article_source_type for row in rows)
        run.status = AutoDbMatchingRun.STATUS_SUCCESS
        run.finished_at = timezone.now()
        run.summary_json = {
            "rows": len(rows),
            "supplier_code": "gpl",
            "rows_by_status": dict(by_status),
            "rows_by_resolver_source": dict(by_resolver),
            "rows_by_article_source": dict(by_article_source),
        }
        run.save(update_fields=["status", "finished_at", "summary_json", "updated_at"])
        materialized = [asdict(item) for item in rows]
        return {
            "run_id": str(run.id),
            "rows_count": len(materialized),
            "rows": materialized,
            "rows_by_status": dict(by_status),
            "rows_by_resolver_source": dict(by_resolver),
            "rows_by_article_source": dict(by_article_source),
        }

    def _write_queue_payload(self, payload: dict[str, Any]) -> None:
        self._write_csv(self.OUTPUT_QUEUE_CSV, payload["rows"])
        paused_keys = {
            "skipped_non_tecdoc",
            "skipped_brand_unresolved",
            "skipped_split_needed",
            "skipped_unsafe_ambiguous",
            "skipped_bad_article_source",
            "quota_paused",
        }
        paused = {k: v for k, v in payload["rows_by_status"].items() if k in paused_keys}
        self._write_md(
            self.OUTPUT_QUEUE_MD,
            title="Matching queue after dev delete + GPL import",
            lines=[
                f"- run_id: {payload['run_id']}",
                f"- queue_size: {payload['rows_count']}",
                f"- rows_by_status: {json.dumps(payload['rows_by_status'], ensure_ascii=False)}",
                f"- rows_by_resolver_source: {json.dumps(payload['rows_by_resolver_source'], ensure_ascii=False)}",
                f"- rows_by_article_source: {json.dumps(payload['rows_by_article_source'], ensure_ascii=False)}",
                f"- paused_buckets: {json.dumps(paused, ensure_ascii=False)}",
            ],
        )

    def _write_final_report(
        self,
        *,
        scope_count: int,
        delete_result: dict[str, Any],
        gpl_dry: dict[str, Any],
        gpl_apply: dict[str, Any],
        queue_payload: dict[str, Any],
        global_before: dict[str, Any],
        global_after: dict[str, Any],
    ) -> None:
        dry_summary = gpl_dry.get("summary") or {}
        apply_summary = gpl_apply.get("summary") or {}
        category_apply = apply_summary.get("gpl_category_assignment") or {}
        photo_apply = apply_summary.get("gpl_image_sync") or {}
        lines = [
            "# Dev delete 1300 + GPL import final report",
            "",
            f"1. Delete scope count: {scope_count}",
            f"2. Products deleted: {delete_result.get('products_deleted', 0)}",
            "3. Dependent rows deleted/cleaned: see /tmp/dev_delete_1300_hard_delete_apply_result.csv",
            f"4. 0S3V5O5M9202 preserved: {Product.objects.filter(svom_sku='0S3V5O5M9202').exists()}",
            f"5. GPL import dry-run result: run={gpl_dry['run_id']} status={gpl_dry['status']}",
            f"6. GPL import apply result: run={gpl_apply['run_id']} status={gpl_apply['status']}",
            f"7. Products created/updated/skipped: created={int(apply_summary.get('offers_created', 0))} updated={int(apply_summary.get('offers_updated', 0))} skipped={int(apply_summary.get('offers_skipped', 0))}",
            f"8. GPL photos created/updated/skipped: created={int(photo_apply.get('created', 0))} reused={int(photo_apply.get('reused', 0))} stale_marked={int(photo_apply.get('stale_marked', 0))}",
            f"9. Categories mapped/review/missing: mapped={int(category_apply.get('category_assigned_total', 0))} review={int((apply_summary.get('category_status_counts') or {}).get('needs_review', 0))} missing_leaf={int(category_apply.get('missing_leaf_category', 0))}",
            "10. Schedule status: see /tmp/gpl_fresh_import_recurring_schedule.md",
            f"11. Matching queue after import: {queue_payload['rows_count']} rows",
            "12. Confirmation: no UTR API, no Auto_DB images, no Auto_DB enrichment, no Product links.",
            "",
            "## Global deltas",
            f"- product_count_delta: {self._delta(global_before, global_after, 'product_count')}",
            f"- supplier_offer_count_delta: {self._delta(global_before, global_after, 'supplier_offer_count')}",
            f"- supplier_raw_offer_count_delta: {self._delta(global_before, global_after, 'supplier_raw_offer_count')}",
            f"- product_price_count_delta: {self._delta(global_before, global_after, 'product_price_count')}",
            f"- linked_by_key_delta: {self._delta(global_before, global_after, 'linked_by_key')}",
            f"- quality_trusted_delta: {self._delta(global_before, global_after, 'quality_trusted')}",
            f"- stock_sum_delta: {self._delta(global_before, global_after, 'supplier_stock_sum')}",
            f"- purchase_sum_delta: {self._delta(global_before, global_after, 'supplier_purchase_sum')}",
            f"- final_price_sum_delta: {self._delta(global_before, global_after, 'productprice_final_sum')}",
        ]
        self.OUTPUT_FINAL_MD.write_text("\n".join(lines), encoding="utf-8")

    def _global_snapshot(self) -> dict[str, Any]:
        def _d(value: Any) -> Decimal:
            if value is None:
                return Decimal("0")
            if isinstance(value, Decimal):
                return value
            return Decimal(str(value))

        return {
            "product_count": Product.objects.count(),
            "supplier_offer_count": SupplierOffer.objects.count(),
            "supplier_raw_offer_count": SupplierRawOffer.objects.count(),
            "product_price_count": ProductPrice.objects.count(),
            "product_attribute_count": ProductAttribute.objects.count(),
            "product_fitment_count": ProductFitment.objects.count(),
            "product_image_count": ProductImage.objects.count(),
            "linked_by_key": Product.objects.exclude(autodb_article_key="").count(),
            "quality_trusted": AutoDbProductLinkQuality.objects.filter(status=AutoDbProductLinkQuality.STATUS_TRUSTED).count(),
            "quality_suspicious": AutoDbProductLinkQuality.objects.filter(status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS).count(),
            "supplier_stock_sum": _d(SupplierOffer.objects.aggregate(v=Sum("stock_qty"))["v"]),
            "supplier_purchase_sum": _d(SupplierOffer.objects.aggregate(v=Sum("purchase_price"))["v"]),
            "productprice_final_sum": _d(ProductPrice.objects.aggregate(v=Sum("final_price"))["v"]),
            "utr_api_calls": 0,
        }

    def _write_model_rows_csv(self, path: Path, queryset) -> None:
        fields = [field.name for field in queryset.model._meta.fields]
        rows = [self._jsonify_values(row) for row in queryset.values(*fields).iterator(chunk_size=5000)]
        self._write_csv(path, rows)

    def _jsonify_values(self, row: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, (dict, list)):
                out[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, Decimal):
                out[key] = str(value)
            elif value is None:
                out[key] = ""
            else:
                out[key] = value
        return out

    def _write_csv(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        headers = list(self._collect_headers(rows))
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in headers})

    def _collect_headers(self, rows: Iterable[dict[str, Any]]) -> list[str]:
        keys: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row.keys():
                if key in seen:
                    continue
                seen.add(key)
                keys.append(key)
        return keys

    def _write_md(self, path: Path, *, title: str, lines: list[str]) -> None:
        body = [f"# {title}", ""]
        body.extend(lines)
        body.append("")
        path.write_text("\n".join(body), encoding="utf-8")

    def _delta(self, before: dict[str, Any], after: dict[str, Any], key: str) -> str:
        a = before.get(key, 0)
        b = after.get(key, 0)
        if isinstance(a, Decimal) or isinstance(b, Decimal):
            return str(Decimal(str(b)) - Decimal(str(a)))
        return str(int(b) - int(a))
