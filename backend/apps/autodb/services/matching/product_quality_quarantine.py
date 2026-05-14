from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.db import transaction

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.catalog.models import Product


@dataclass(frozen=True)
class AutoDbProductQualityQuarantinePlanItem:
    product_id: str
    status: str
    reason: str
    sku: str
    bucket: str


@dataclass(frozen=True)
class AutoDbProductQualityQuarantineResultItem:
    product_id: str
    sku: str
    status: str
    reason: str
    action: str
    job_id: str
    safety: str


class AutoDbProductQualityQuarantineService:
    """
    Applies product-level quarantine in matching service state only.

    Writes only:
    - AutoDbMatchJob (service state)
    - AutoDbMatchEvidence (audit evidence)
    """

    ARTICLE_SOURCE = "product_quality_quarantine"
    RESOLVER_SOURCE = "product_quality_quarantine"
    EVIDENCE_STAGE = "product_quality_quarantine"
    EVIDENCE_SOURCE = "matching_service"
    EVIDENCE_RESULT = "quarantined"
    ALLOWED_STATUSES = {
        "skipped_split_product_candidate",
        "skipped_multi_offer_conflict",
        "needs_review",
        "needs_review_trusted_conflict",
    }

    def load_plan(self, *, csv_path: str | Path) -> tuple[list[AutoDbProductQualityQuarantinePlanItem], list[str]]:
        path = Path(csv_path)
        if not path.exists():
            return [], [f"plan file not found: {path}"]
        rows: list[AutoDbProductQualityQuarantinePlanItem] = []
        errors: list[str] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for idx, raw in enumerate(reader, start=2):
                product_id = str(raw.get("product_id") or "").strip()
                status = str(raw.get("quarantine_status") or "").strip()
                reason = str(raw.get("quarantine_reason") or "").strip()
                sku = str(raw.get("SKU") or "").strip()
                bucket = str(raw.get("bucket") or "").strip()
                if not product_id:
                    errors.append(f"line {idx}: empty product_id")
                    continue
                if status not in self.ALLOWED_STATUSES:
                    errors.append(f"line {idx}: unsupported status {status!r}")
                    continue
                rows.append(
                    AutoDbProductQualityQuarantinePlanItem(
                        product_id=product_id,
                        status=status,
                        reason=reason or status,
                        sku=sku,
                        bucket=bucket,
                    )
                )
        return rows, errors

    def apply_plan(
        self,
        *,
        plan: list[AutoDbProductQualityQuarantinePlanItem],
        dry_run: bool = True,
    ) -> tuple[list[AutoDbProductQualityQuarantineResultItem], dict[str, Any]]:
        if not plan:
            return [], self._summary(
                products_input=0,
                jobs_affected=0,
                would_create=0,
                would_update=0,
                skipped_already_quarantined=0,
                missing_products=0,
                invalid_status_rows=0,
                status_counter={},
            )

        by_product: dict[str, AutoDbProductQualityQuarantinePlanItem] = {}
        duplicate_conflicts = 0
        for item in plan:
            existing = by_product.get(item.product_id)
            if existing is not None and (existing.status != item.status or existing.reason != item.reason):
                duplicate_conflicts += 1
            by_product[item.product_id] = item

        product_ids = list(by_product.keys())
        products = {
            str(item.id): item
            for item in Product.objects.filter(id__in=product_ids).only("id", "svom_sku", "autodb_supplier_id", "display_brand_name")
        }
        existing_jobs_raw = (
            AutoDbMatchJob.objects.filter(
                product_id__in=product_ids,
                supplier_offer__isnull=True,
                article_source_type=self.ARTICLE_SOURCE,
            )
            .order_by("product_id", "-updated_at", "-created_at")
            .iterator(chunk_size=2000)
        )
        existing_jobs: dict[str, AutoDbMatchJob] = {}
        for job in existing_jobs_raw:
            pid = str(job.product_id)
            if pid not in existing_jobs:
                existing_jobs[pid] = job

        results: list[AutoDbProductQualityQuarantineResultItem] = []
        would_create = 0
        would_update = 0
        skipped = 0
        missing_products = 0
        jobs_affected = 0
        status_counter: dict[str, int] = {}

        for pid in sorted(product_ids):
            plan_item = by_product[pid]
            product = products.get(pid)
            if product is None:
                missing_products += 1
                results.append(
                    AutoDbProductQualityQuarantineResultItem(
                        product_id=pid,
                        sku=plan_item.sku,
                        status=plan_item.status,
                        reason=plan_item.reason,
                        action="skipped_missing_product",
                        job_id="",
                        safety="missing_product",
                    )
                )
                continue

            status_counter[plan_item.status] = int(status_counter.get(plan_item.status, 0)) + 1
            existing_job = existing_jobs.get(pid)
            metadata = {
                "quarantine": {
                    "active": True,
                    "source": "product_quality_multioffer_quarantine_plan",
                    "status": plan_item.status,
                    "reason": plan_item.reason,
                    "bucket": plan_item.bucket,
                }
            }
            current_is_same = (
                existing_job is not None
                and str(existing_job.status or "") == plan_item.status
                and str(existing_job.last_error or "") == plan_item.reason
                and isinstance(existing_job.metadata_json, dict)
                and bool(existing_job.metadata_json.get("quarantine", {}).get("active"))
                and str(existing_job.metadata_json.get("quarantine", {}).get("status") or "") == plan_item.status
            )
            if current_is_same:
                skipped += 1
                results.append(
                    AutoDbProductQualityQuarantineResultItem(
                        product_id=pid,
                        sku=str(product.svom_sku or plan_item.sku or ""),
                        status=plan_item.status,
                        reason=plan_item.reason,
                        action="skipped_already_quarantined",
                        job_id=str(existing_job.id),
                        safety="ok",
                    )
                )
                continue

            if existing_job is None:
                would_create += 1
                action = "would_create" if dry_run else "created"
            else:
                would_update += 1
                action = "would_update" if dry_run else "updated"
            jobs_affected += 1

            if not dry_run:
                with transaction.atomic():
                    if existing_job is None:
                        existing_job = AutoDbMatchJob.objects.create(
                            product=product,
                            supplier_offer=None,
                            supplier_code="",
                            raw_brand=str(product.display_brand_name or ""),
                            normalized_brand="",
                            resolved_supplier_id=int(product.autodb_supplier_id or 0) or None,
                            article_source_type=self.ARTICLE_SOURCE,
                            article_value="",
                            canonical_article="",
                            status=plan_item.status,
                            last_error=plan_item.reason,
                            metadata_json=metadata,
                        )
                    else:
                        existing_job.status = plan_item.status
                        existing_job.last_error = plan_item.reason
                        existing_job.article_source_type = self.ARTICLE_SOURCE
                        existing_job.metadata_json = metadata
                        existing_job.save(
                            update_fields=[
                                "status",
                                "last_error",
                                "article_source_type",
                                "metadata_json",
                                "updated_at",
                            ]
                        )
                    AutoDbMatchEvidence.objects.create(
                        job=existing_job,
                        stage=self.EVIDENCE_STAGE,
                        source=self.EVIDENCE_SOURCE,
                        result=self.EVIDENCE_RESULT,
                        supplier_id=int(product.autodb_supplier_id or 0) or None,
                        article_value="",
                        canonical_article="",
                        reason=plan_item.reason,
                        payload_json={
                            "status": plan_item.status,
                            "reason": plan_item.reason,
                            "bucket": plan_item.bucket,
                            "product_id": plan_item.product_id,
                            "sku": plan_item.sku,
                        },
                    )

            results.append(
                AutoDbProductQualityQuarantineResultItem(
                    product_id=pid,
                    sku=str(product.svom_sku or plan_item.sku or ""),
                    status=plan_item.status,
                    reason=plan_item.reason,
                    action=action,
                    job_id=str(existing_job.id) if existing_job is not None else "",
                    safety="ok",
                )
            )

        summary = self._summary(
            products_input=len(product_ids),
            jobs_affected=jobs_affected,
            would_create=would_create,
            would_update=would_update,
            skipped_already_quarantined=skipped,
            missing_products=missing_products,
            invalid_status_rows=0,
            status_counter=status_counter,
            duplicate_conflicts=duplicate_conflicts,
            dry_run=dry_run,
        )
        return results, summary

    def _summary(self, **values: Any) -> dict[str, Any]:
        base = {
            "products_input": 0,
            "jobs_affected": 0,
            "would_create": 0,
            "would_update": 0,
            "skipped_already_quarantined": 0,
            "missing_products": 0,
            "invalid_status_rows": 0,
            "duplicate_conflicts": 0,
            "status_counter": {},
            "dry_run": True,
        }
        base.update(values)
        return base

