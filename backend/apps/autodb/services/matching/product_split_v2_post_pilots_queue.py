from __future__ import annotations

import ast
import csv
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.db import transaction
from django.db.models import Q, Sum

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.autodb.services.matching.job_builder import AutoDbMatchJobBuilder
from apps.autodb.services.matching.reports import write_report
from apps.catalog.models import AutoDbProductLinkQuality, Product, ProductAttribute, ProductImage
from apps.catalog.services.product_sku import get_product_display_sku
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer


class AutoDbProductSplitV2PostPilotsQueueService:
    EVIDENCE_STAGE = "product_split_v2_reconciliation"

    def __init__(self):
        self.out = Path("/tmp")
        self.builder = AutoDbMatchJobBuilder()
        self.pilot_result_paths = [
            Path("/tmp/product_quality_0S3V5O5M9202_split_v2_apply_result.csv"),
            Path("/tmp/product_quality_split_v2_one_apply_result.csv"),
        ]
        self.split_candidates_path = Path("/tmp/product_quality_split_candidates_dry_run.csv")
        self.resolved_search_path = Path("/tmp/product_quality_split_v2_resolved_brand_candidate_search.csv")

    def run(self, *, apply_reconciliation: bool = True) -> dict[str, Any]:
        before = self._integrity_snapshot()
        pilots = self._load_pilots()

        state_rows = self._pilots_state_rows(pilots)
        write_report(
            command_name="product_quality_split_v2_two_pilots_state_verification",
            run_id=None,
            rows=state_rows,
            title="Split v2 two pilots state verification",
            summary={"pilots": len(pilots)},
            export_prefix="/tmp/product_quality_split_v2_two_pilots_state_verification",
        )

        sku_visibility_md = self._sku_visibility_audit(pilots)
        (self.out / "product_quality_split_v2_sku_visibility_audit.md").write_text(sku_visibility_md, encoding="utf-8")

        queue_rows, queue_summary = self._build_quality_queue()
        write_report(
            command_name="product_quality_queue_after_split_v2_pilots",
            run_id=None,
            rows=queue_rows,
            title="Product quality queue after split v2 pilots",
            summary=queue_summary,
            export_prefix="/tmp/product_quality_queue_after_split_v2_pilots",
        )

        reconciliation_dry_rows, reconciliation_dry_summary = self._reconciliation_plan(pilots)
        write_report(
            command_name="product_quality_split_v2_quarantine_reconciliation_dry_run",
            run_id=None,
            rows=reconciliation_dry_rows,
            title="Split v2 quarantine reconciliation dry-run",
            summary=reconciliation_dry_summary,
            export_prefix="/tmp/product_quality_split_v2_quarantine_reconciliation_dry_run",
        )

        reconciliation_apply_rows, reconciliation_apply_summary = self._reconciliation_apply(
            dry_rows=reconciliation_dry_rows,
            apply_reconciliation=apply_reconciliation,
        )
        write_report(
            command_name="product_quality_split_v2_quarantine_reconciliation_apply_result",
            run_id=None,
            rows=reconciliation_apply_rows,
            title="Split v2 quarantine reconciliation apply result",
            summary=reconciliation_apply_summary,
            export_prefix="/tmp/product_quality_split_v2_quarantine_reconciliation_apply_result",
        )

        remaining_rows, remaining_summary = self._remaining_candidates_status(pilots)
        write_report(
            command_name="product_quality_split_v2_remaining_candidates_status",
            run_id=None,
            rows=remaining_rows,
            title="Split v2 remaining candidates status",
            summary=remaining_summary,
            export_prefix="/tmp/product_quality_split_v2_remaining_candidates_status",
        )

        after = self._integrity_snapshot()
        integrity_rows = self._integrity_rows(before=before, after=after)
        write_report(
            command_name="product_quality_split_v2_post_pilots_queue_integrity",
            run_id=None,
            rows=integrity_rows,
            title="Split v2 post pilots queue integrity",
            summary={"allowed_state_writes": "AutoDbMatchJob/AutoDbMatchEvidence only", "utr_api_calls": 0},
            export_prefix="/tmp/product_quality_split_v2_post_pilots_queue_integrity",
        )

        final_report = self._final_report(
            pilots=pilots,
            queue_summary=queue_summary,
            reconciliation_apply_summary=reconciliation_apply_summary,
            remaining_summary=remaining_summary,
        )
        (self.out / "product_quality_split_v2_post_pilots_queue_final_report.md").write_text(final_report, encoding="utf-8")

        return {
            "pilots": pilots,
            "queue_summary": queue_summary,
            "reconciliation_apply_summary": reconciliation_apply_summary,
            "remaining_summary": remaining_summary,
        }

    def _load_pilots(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.pilot_result_paths:
            if not path.exists():
                continue
            data = self._read_csv(path)
            if not data:
                continue
            row = data[0]
            rows.append(
                {
                    "result_path": str(path),
                    "source_product_id": str(row.get("source_product_id") or "").strip(),
                    "new_product_id": str(row.get("new_product_id") or "").strip(),
                    "new_product_sku": str(row.get("new_product_sku") or "").strip(),
                    "new_product_svom_sku": str(row.get("new_product_svom_sku") or "").strip(),
                    "moved_offer_ids": self._parse_tuple_csv(row.get("moved_offer_ids")),
                    "moved_raw_offer_ids": self._parse_tuple_csv(row.get("moved_raw_offer_ids")),
                    "source_productprice_ids": self._parse_tuple_csv(row.get("source_productprice_ids")),
                    "new_productprice_id": str(row.get("new_productprice_id") or "").strip(),
                }
            )
        if len(rows) < 2:
            raise RuntimeError(f"Expected 2 pilot result rows, got {len(rows)}")
        return rows

    def _pilots_state_rows(self, pilots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for idx, pilot in enumerate(pilots, start=1):
            source = Product.objects.select_related("brand").get(id=pilot["source_product_id"])
            new = Product.objects.select_related("brand").get(id=pilot["new_product_id"])

            source_offers = list(SupplierOffer.objects.filter(product=source).select_related("supplier").order_by("id"))
            new_offers = list(SupplierOffer.objects.filter(product=new).select_related("supplier").order_by("id"))
            source_raw = list(SupplierRawOffer.objects.filter(matched_product=source).select_related("source").order_by("id"))
            new_raw = list(SupplierRawOffer.objects.filter(matched_product=new).select_related("source").order_by("id"))
            source_prices = list(ProductPrice.objects.filter(product=source).order_by("id"))
            new_prices = list(ProductPrice.objects.filter(product=new).order_by("id"))

            source_quarantine = self._latest_quarantine_job(source.id)
            new_quarantine = self._latest_quarantine_job(new.id)

            out.append(
                {
                    "pilot": idx,
                    "role": "source_product",
                    "product_id": str(source.id),
                    "internal_sku": str(source.sku or ""),
                    "public_sku": str(source.svom_sku or ""),
                    "display_sku_runtime": get_product_display_sku(source),
                    "brand": str(source.brand.name or ""),
                    "display_brand_name": str(source.display_brand_name or ""),
                    "autodb_supplier_id": int(source.autodb_supplier_id or 0),
                    "supplier_offer_ids": ",".join(str(item.id) for item in source_offers),
                    "supplier_offer_codes": ",".join(sorted({str(item.supplier.code or "").lower() for item in source_offers})),
                    "supplier_offer_stock_sum": str(sum(int(item.stock_qty or 0) for item in source_offers)),
                    "raw_offer_ids": ",".join(str(item.id) for item in source_raw),
                    "raw_offer_source_codes": ",".join(sorted({str(getattr(item.source, 'code', '') or '').lower() for item in source_raw})),
                    "productprice_ids": ",".join(str(item.id) for item in source_prices),
                    "productprice_final_sum": str(sum((item.final_price or 0) for item in source_prices)),
                    "linked_by_key": bool(str(source.autodb_article_key or "").strip()),
                    "quality_trusted": AutoDbProductLinkQuality.objects.filter(
                        product=source, status=AutoDbProductLinkQuality.STATUS_TRUSTED
                    ).exists(),
                    "quarantine_job_id": str(getattr(source_quarantine, "id", "") or ""),
                    "quarantine_status": str(getattr(source_quarantine, "status", "") or ""),
                    "quarantine_reason": str(getattr(source_quarantine, "last_error", "") or ""),
                    "quarantine_active": self._quarantine_active(source_quarantine),
                }
            )
            out.append(
                {
                    "pilot": idx,
                    "role": "new_product",
                    "product_id": str(new.id),
                    "internal_sku": str(new.sku or ""),
                    "public_sku": str(new.svom_sku or ""),
                    "display_sku_runtime": get_product_display_sku(new),
                    "brand": str(new.brand.name or ""),
                    "display_brand_name": str(new.display_brand_name or ""),
                    "autodb_supplier_id": int(new.autodb_supplier_id or 0),
                    "supplier_offer_ids": ",".join(str(item.id) for item in new_offers),
                    "supplier_offer_codes": ",".join(sorted({str(item.supplier.code or "").lower() for item in new_offers})),
                    "supplier_offer_stock_sum": str(sum(int(item.stock_qty or 0) for item in new_offers)),
                    "raw_offer_ids": ",".join(str(item.id) for item in new_raw),
                    "raw_offer_source_codes": ",".join(sorted({str(getattr(item.source, 'code', '') or '').lower() for item in new_raw})),
                    "productprice_ids": ",".join(str(item.id) for item in new_prices),
                    "productprice_final_sum": str(sum((item.final_price or 0) for item in new_prices)),
                    "linked_by_key": bool(str(new.autodb_article_key or "").strip()),
                    "quality_trusted": AutoDbProductLinkQuality.objects.filter(
                        product=new, status=AutoDbProductLinkQuality.STATUS_TRUSTED
                    ).exists(),
                    "quarantine_job_id": str(getattr(new_quarantine, "id", "") or ""),
                    "quarantine_status": str(getattr(new_quarantine, "status", "") or ""),
                    "quarantine_reason": str(getattr(new_quarantine, "last_error", "") or ""),
                    "quarantine_active": self._quarantine_active(new_quarantine),
                }
            )
        return out

    def _sku_visibility_audit(self, pilots: list[dict[str, Any]]) -> str:
        lines = [
            "# Split v2 SKU visibility audit",
            "",
            "## Runtime display rules",
            "- Public/catalog serializers use `get_product_display_sku()` for `sku`.",
            "- `get_product_display_sku()` returns `svom_sku` first when present.",
            "- Backoffice serializer rewrites `payload[\"sku\"]` to display SKU and keeps `internal_import_key` as internal `sku`.",
            "",
            "## Pilot checks",
        ]
        for pilot in pilots:
            new = Product.objects.get(id=pilot["new_product_id"])
            lines.extend(
                [
                    f"- product_id={new.id}",
                    f"  - internal_sku={new.sku}",
                    f"  - public_sku(svom_sku)={new.svom_sku}",
                    f"  - runtime_display_sku={get_product_display_sku(new)}",
                    f"  - storefront_user_facing_expected={new.svom_sku}",
                    f"  - admin_payload_sku_expected={get_product_display_sku(new)}",
                    f"  - admin_internal_import_key_expected={new.sku}",
                ]
            )
        lines.append("")
        return "\n".join(lines)

    def _build_quality_queue(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        total_offers = SupplierOffer.objects.count()
        limit = max(1, min(total_offers, 50000))
        rows = [asdict(item) for item in self.builder.build_jobs(run=None, supplier_code="", limit=limit, dry_run=True)]
        by_status = Counter(str(item.get("status") or "") for item in rows)
        by_supplier = Counter(str(item.get("supplier_code") or "") for item in rows)

        target_products = self._pilot_product_ids()
        target_rows = [item for item in rows if str(item.get("product_id") or "") in target_products]
        target_status = {pid: [] for pid in target_products}
        for item in target_rows:
            target_status[str(item.get("product_id") or "")].append(str(item.get("status") or ""))

        summary = {
            "queue_size": len(rows),
            "supplier_offer_total": int(total_offers),
            "queue_limit_used": int(limit),
            "queue_is_limited_sample": limit < total_offers,
            "skipped_split_product_candidate": int(by_status.get("skipped_split_product_candidate", 0)),
            "skipped_multi_offer_conflict": int(by_status.get("skipped_multi_offer_conflict", 0)),
            "needs_review": int(by_status.get("needs_review", 0)),
            "rows_by_status": dict(by_status),
            "rows_by_supplier_code_top_20": dict(by_supplier.most_common(20)),
            "target_pilot_statuses": target_status,
        }
        return rows, summary

    def _reconciliation_plan(self, pilots: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        source_ids = {str(item["source_product_id"]) for item in pilots}
        all_ids = {str(item["source_product_id"]) for item in pilots} | {str(item["new_product_id"]) for item in pilots}

        # 1) Resolve stale split/multi-offer jobs on original products.
        stale_jobs = AutoDbMatchJob.objects.filter(
            product_id__in=list(source_ids),
            status__in=["skipped_split_product_candidate", "skipped_multi_offer_conflict"],
        ).select_related("supplier_offer")
        for job in stale_jobs:
            actions.append(
                {
                    "action": "resolve_conflict_job_by_split_v2",
                    "job_id": str(job.id),
                    "product_id": str(job.product_id),
                    "supplier_offer_id": str(job.supplier_offer_id or ""),
                    "current_status": str(job.status or ""),
                    "current_reason": str(job.last_error or ""),
                    "next_status": "rejected",
                    "next_reason": "resolved_by_split_v2",
                    "apply_supported": True,
                }
            )

        # 2) Resolve inconsistent jobs where supplier_offer moved to another product.
        moved_jobs = AutoDbMatchJob.objects.filter(product_id__in=list(all_ids)).exclude(supplier_offer__isnull=True).select_related("supplier_offer")
        for job in moved_jobs:
            offer_product_id = str(getattr(getattr(job, "supplier_offer", None), "product_id", "") or "")
            if offer_product_id and offer_product_id != str(job.product_id):
                actions.append(
                    {
                        "action": "resolve_inconsistent_offer_binding_job",
                        "job_id": str(job.id),
                        "product_id": str(job.product_id),
                        "supplier_offer_id": str(job.supplier_offer_id or ""),
                        "current_status": str(job.status or ""),
                        "current_reason": str(job.last_error or ""),
                        "next_status": "rejected",
                        "next_reason": "resolved_by_split_v2_offer_rebound",
                        "apply_supported": True,
                    }
                )

        # 3) Release quarantine only when non-quarantine simulation is safe/new.
        for product_id in sorted(all_ids):
            product = Product.objects.get(id=product_id)
            qjob = self._latest_quarantine_job(product_id)
            if qjob is None or not self._quarantine_active(qjob):
                continue
            simulated = self._simulate_without_quarantine(product_id=product_id)
            simulated_statuses = sorted({str(item.get("status") or "") for item in simulated})
            safe = bool(simulated_statuses) and all(item == "new" for item in simulated_statuses)
            actions.append(
                {
                    "action": "release_quarantine_if_safe",
                    "job_id": str(qjob.id),
                    "product_id": str(product_id),
                    "supplier_offer_id": "",
                    "current_status": str(qjob.status or ""),
                    "current_reason": str(qjob.last_error or ""),
                    "next_status": str(qjob.status or ""),
                    "next_reason": "quarantine_released_by_split_v2" if safe else "keep_quarantine_needs_review",
                    "simulated_statuses_without_quarantine": ";".join(simulated_statuses),
                    "apply_supported": safe,
                }
            )

        summary = {
            "actions_total": len(actions),
            "actions_by_type": dict(Counter(str(item.get("action") or "") for item in actions)),
            "applicable_actions": sum(1 for item in actions if bool(item.get("apply_supported"))),
        }
        return actions, summary

    def _reconciliation_apply(
        self,
        *,
        dry_rows: list[dict[str, Any]],
        apply_reconciliation: bool,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        results: list[dict[str, Any]] = []
        summary = Counter()

        for item in dry_rows:
            action = str(item.get("action") or "")
            job_id = str(item.get("job_id") or "")
            supported = bool(item.get("apply_supported"))
            if not apply_reconciliation or not supported:
                results.append(
                    {
                        **item,
                        "apply_action": "dry_run_only" if apply_reconciliation else "apply_disabled",
                        "applied": False,
                    }
                )
                continue

            job = AutoDbMatchJob.objects.filter(id=job_id).first()
            if job is None:
                results.append({**item, "apply_action": "skipped_missing_job", "applied": False})
                summary["skipped_missing_job"] += 1
                continue

            with transaction.atomic():
                if action in {"resolve_conflict_job_by_split_v2", "resolve_inconsistent_offer_binding_job"}:
                    meta = job.metadata_json if isinstance(job.metadata_json, dict) else {}
                    split_meta = meta.get("split_v2_reconciliation", {}) if isinstance(meta.get("split_v2_reconciliation"), dict) else {}
                    split_meta.update(
                        {
                            "resolved": True,
                            "resolved_at": datetime.now(timezone.utc).isoformat(),
                            "action": action,
                        }
                    )
                    meta["split_v2_reconciliation"] = split_meta
                    job.status = "rejected"
                    job.last_error = str(item.get("next_reason") or "resolved_by_split_v2")
                    job.metadata_json = meta
                    job.save(update_fields=["status", "last_error", "metadata_json", "updated_at"])
                    AutoDbMatchEvidence.objects.create(
                        job=job,
                        stage=self.EVIDENCE_STAGE,
                        source="matching_service",
                        result="resolved_by_split_v2",
                        supplier_id=int(job.resolved_supplier_id or 0) or None,
                        article_value=job.article_value or "",
                        canonical_article=job.canonical_article or "",
                        reason=str(item.get("next_reason") or "resolved_by_split_v2"),
                        payload_json={"action": action, "product_id": str(job.product_id)},
                    )
                    summary["resolved_jobs"] += 1
                    results.append({**item, "apply_action": "updated", "applied": True})
                elif action == "release_quarantine_if_safe":
                    meta = job.metadata_json if isinstance(job.metadata_json, dict) else {}
                    quarantine = meta.get("quarantine", {}) if isinstance(meta.get("quarantine"), dict) else {}
                    quarantine["active"] = False
                    quarantine["resolved_by_split_v2"] = True
                    quarantine["resolved_at"] = datetime.now(timezone.utc).isoformat()
                    meta["quarantine"] = quarantine
                    job.last_error = "quarantine_released_by_split_v2"
                    job.metadata_json = meta
                    job.save(update_fields=["last_error", "metadata_json", "updated_at"])
                    AutoDbMatchEvidence.objects.create(
                        job=job,
                        stage=self.EVIDENCE_STAGE,
                        source="matching_service",
                        result="quarantine_released",
                        supplier_id=int(job.resolved_supplier_id or 0) or None,
                        article_value=job.article_value or "",
                        canonical_article=job.canonical_article or "",
                        reason="quarantine_released_by_split_v2",
                        payload_json={"action": action, "product_id": str(job.product_id)},
                    )
                    summary["released_quarantine_jobs"] += 1
                    results.append({**item, "apply_action": "updated", "applied": True})
                else:
                    results.append({**item, "apply_action": "skipped_unsupported_action", "applied": False})
                    summary["skipped_unsupported_action"] += 1

        summary["actions_total"] = len(dry_rows)
        summary["applied"] = sum(1 for row in results if bool(row.get("applied")))
        summary["dry_only"] = sum(1 for row in results if not bool(row.get("applied")))
        return results, dict(summary)

    def _remaining_candidates_status(self, pilots: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        source_rows = self._read_csv(self.split_candidates_path)
        total = sum(
            1
            for row in source_rows
            if str(row.get("recommended_action") or "") in {"split_product_candidate", "split_product_after_manual_review"}
        )
        split_source_ids = {str(item["source_product_id"]) for item in pilots}

        search_rows = self._read_csv(self.resolved_search_path)
        # Re-evaluate only for known applied source IDs: remove from clean pool if already split.
        clean_selected = [
            row
            for row in search_rows
            if str(row.get("search_decision") or "") == "selected_for_resolved_batch"
            and str(row.get("product_id") or "") not in split_source_ids
        ]
        needs_brand = [
            row
            for row in search_rows
            if str(row.get("search_decision") or "") == "needs_brand_resolution"
            and str(row.get("product_id") or "") not in split_source_ids
        ]
        blocked = [
            row
            for row in search_rows
            if str(row.get("search_decision") or "") == "blocked"
            and str(row.get("product_id") or "") not in split_source_ids
        ]

        out = [
            {
                "metric": "total_original_split_product_candidate",
                "value": total,
            },
            {
                "metric": "already_split_successfully",
                "value": len(split_source_ids),
            },
            {
                "metric": "clean_resolved_brand_remaining",
                "value": len(clean_selected),
            },
            {
                "metric": "needs_brand_resolution",
                "value": len(needs_brand),
            },
            {
                "metric": "blocked",
                "value": len(blocked),
            },
            {
                "metric": "display_only_policy_candidates",
                "value": len(needs_brand),
            },
            {
                "metric": "recommended_next_action",
                "value": "continue one-by-one clean resolved-brand apply; keep brand-unresolved in review until policy approved",
            },
        ]
        summary = {item["metric"]: item["value"] for item in out}
        return out, summary

    def _final_report(
        self,
        *,
        pilots: list[dict[str, Any]],
        queue_summary: dict[str, Any],
        reconciliation_apply_summary: dict[str, Any],
        remaining_summary: dict[str, Any],
    ) -> str:
        target_status = queue_summary.get("target_pilot_statuses", {})
        lines = [
            "# Split v2 post pilots queue final report",
            "",
            "1. Final state of both split pilots: see /tmp/product_quality_split_v2_two_pilots_state_verification.csv/.md",
            "2. SKU visibility result: see /tmp/product_quality_split_v2_sku_visibility_audit.md",
            f"3. Queue size after pilots: {queue_summary.get('queue_size', 0)} (limit_used={queue_summary.get('queue_limit_used', 0)})",
            f"4. Split originals no longer blocked incorrectly: reconciliation_applied={reconciliation_apply_summary.get('applied', 0)}",
            f"5. New split products normal-matching eligibility by queue state: {target_status}",
            f"6. Remaining clean split candidates: {remaining_summary.get('clean_resolved_brand_remaining', 0)}",
            f"7. Remaining unresolved/display-only candidates: {remaining_summary.get('display_only_policy_candidates', 0)}",
            "8. Safety confirmation:",
            "   - no Product/SupplierOffer/SupplierRawOffer/ProductPrice writes",
            "   - no links",
            "   - no enrichment",
            "   - no images",
            "   - no import",
            "   - no UTR API",
            "   - no price/stock value changes",
            "   - optional writes were only service-state (AutoDbMatchJob/AutoDbMatchEvidence) in Task D.",
            "",
        ]
        return "\n".join(lines)

    def _simulate_without_quarantine(self, *, product_id: str) -> list[dict[str, Any]]:
        offers = list(SupplierOffer.objects.select_related("supplier", "product", "product__brand").filter(product_id=product_id).order_by("-updated_at"))
        if not offers:
            return []
        raw_map = self.builder._latest_raw_offer_map(offers=offers)  # noqa: SLF001
        trusted_map = self.builder._trusted_link_map(offers=offers)  # noqa: SLF001
        guard_map = self.builder.multi_offer_classifier.classify_from_offers(offers=offers, raw_offer_map=raw_map)
        rows: list[dict[str, Any]] = []
        for offer in offers:
            built = self.builder._build_from_offer(  # noqa: SLF001
                offer=offer,
                run=None,
                dry_run=True,
                raw_offer=raw_map.get((str(offer.product_id), str(offer.supplier_id))),
                trusted_link_exists=trusted_map.get(str(offer.product_id), False),
                multi_offer_guard=guard_map.get(str(offer.product_id)),
                product_quarantine=None,
            )
            rows.append(asdict(built))
        return rows

    def _latest_quarantine_job(self, product_id: str) -> AutoDbMatchJob | None:
        return (
            AutoDbMatchJob.objects.filter(
                product_id=product_id,
                supplier_offer__isnull=True,
                article_source_type="product_quality_quarantine",
            )
            .order_by("-updated_at", "-created_at")
            .first()
        )

    def _quarantine_active(self, job: AutoDbMatchJob | None) -> bool:
        if job is None:
            return False
        meta = job.metadata_json if isinstance(job.metadata_json, dict) else {}
        quarantine = meta.get("quarantine") if isinstance(meta.get("quarantine"), dict) else {}
        return bool(quarantine.get("active", True))

    def _pilot_product_ids(self) -> set[str]:
        ids: set[str] = set()
        for row in self._load_pilots():
            ids.add(str(row["source_product_id"]))
            ids.add(str(row["new_product_id"]))
        return ids

    def _integrity_snapshot(self) -> dict[str, Any]:
        return {
            "product_count": Product.objects.count(),
            "supplieroffer_count": SupplierOffer.objects.count(),
            "supplierrawoffer_count": SupplierRawOffer.objects.count(),
            "productprice_count": ProductPrice.objects.count(),
            "productattribute_count": ProductAttribute.objects.count(),
            "productfitment_count": ProductFitment.objects.count(),
            "productimage_count": ProductImage.objects.count(),
            "linked_by_key_count": Product.objects.exclude(autodb_article_key="").count(),
            "quality_trusted_count": AutoDbProductLinkQuality.objects.filter(status=AutoDbProductLinkQuality.STATUS_TRUSTED).count(),
            "sum_supplier_stock_qty": SupplierOffer.objects.aggregate(v=Sum("stock_qty"))["v"] or 0,
            "sum_supplier_purchase_price": SupplierOffer.objects.aggregate(v=Sum("purchase_price"))["v"] or 0,
            "sum_productprice_final_price": ProductPrice.objects.aggregate(v=Sum("final_price"))["v"] or 0,
            "autodb_match_job_count": AutoDbMatchJob.objects.count(),
            "autodb_match_evidence_count": AutoDbMatchEvidence.objects.count(),
            "utr_api_calls": 0,
        }

    def _integrity_rows(self, *, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            b = before.get(key)
            a = after.get(key)
            delta: Any = ""
            try:
                delta = (a or 0) - (b or 0)
            except Exception:
                delta = ""
            out.append({"metric": key, "before": b, "after": a, "delta": delta, "changed": b != a})
        return out

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    def _parse_tuple_csv(self, value: Any) -> list[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, (list, tuple, set)):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
        return [item.strip() for item in raw.split(",") if item.strip()]

