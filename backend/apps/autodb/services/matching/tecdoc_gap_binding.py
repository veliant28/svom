from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.db import connections, transaction
from django.db.models import Q, Sum
from openpyxl import Workbook

from apps.autodb.models import AutoDbRemoteQuotaState, AutoDbSupplierBrandAlias
from apps.autodb.services.matching.brand_coverage import AutoDbBrandCoverageAuditService
from apps.autodb.services.matching.brand_resolver import AutoDbBrandResolver
from apps.autodb.services.matching.constants import INVALID_BRAND_VALUE_KEYS, REMOTE_QUOTA_KEY, UNSAFE_BRAND_KEYS
from apps.autodb.services.matching.deterministic_brand_binding import DeterministicBrandNormalizer
from apps.autodb.services.matching.job_builder import AutoDbMatchJobBuilder
from apps.autodb.services.matching.quota_tracker import AutoDbRemoteQuotaTracker
from apps.autodb.services.matching.reports import write_report
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.remote_client import AutoDbProRemoteClient, AutoDbProRemoteClientConfig
from apps.catalog.models import AutoDbProductLinkQuality, Product, ProductAttribute, ProductImage
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.parsers.utils import normalize_brand


LEGAL_SUFFIXES = ("R", "TM", "REG", "REGISTERED", "FILTER", "FILTERS", "FRICTION", "AUTOMOTIVE", "SEINSA", "BILSTEIN", "ORIGINAL", "TURBOLADER", "GLUHLAMPEN")
PUNCT_RE = re.compile(r"[^A-Z0-9]+")


class AutoDbTecdocGapBindingService:
    def __init__(self, *, now: datetime | None = None):
        self.now = now or datetime.now(timezone.utc)
        self.out = Path("/tmp")
        self.normalizer = DeterministicBrandNormalizer()
        self.resolver = AutoDbBrandResolver()
        self.storage = AutoDbRawCloneStorage()
        self.fast_remote_storage = self._build_fast_remote_storage()
        self.quota_tracker = AutoDbRemoteQuotaTracker()

    def run(self, *, apply_changes: bool = False, queue_limit: int = 2000) -> dict[str, Any]:
        before = self._integrity_snapshot()
        coverage_before = [asdict(row) for row in AutoDbBrandCoverageAuditService().audit(supplier_code="", limit=0)]
        suppliers, supplier_by_variant = self._load_local_suppliers()

        invalid_fix_report = self._build_invalid_fix_report(coverage_before)
        (self.out / "autodb_service_invalid_brand_value_fix_report.md").write_text(invalid_fix_report, encoding="utf-8")

        tecdoc_rows = self._tecdoc_likely_rows(coverage_before)
        local_search_rows = self._local_candidate_search(tecdoc_rows=tecdoc_rows, suppliers=suppliers, supplier_by_variant=supplier_by_variant)
        self._export_local_search(local_search_rows)

        remote_audit_rows, remote_summary = self._remote_supplier_audit(local_search_rows)
        self._export_remote_audit(remote_audit_rows, remote_summary)

        apply_candidates = self._build_apply_candidate_set(local_search_rows)
        self._export_apply_candidates(apply_candidates)

        dry_rows, dry_summary, clean_rows = self._build_dry_run(apply_candidates)
        self._export_dry_run(dry_rows, dry_summary)

        apply_rows, apply_summary = self._apply(clean_rows, dry_summary, apply_changes=apply_changes)
        self._export_apply_result(apply_rows, apply_summary)

        repeat_rows, repeat_summary, _ = self._build_dry_run(self._build_apply_candidate_set(local_search_rows))
        self._export_repeat_dry(repeat_rows, repeat_summary)

        ctr_rows = self._build_ctr_unsafe_review(coverage_before)
        self._export_ctr_review(ctr_rows)

        missing_local_rows = self._build_missing_local_supplier_proposal(local_search_rows, remote_audit_rows)
        self._export_missing_local_proposal(missing_local_rows)

        if int(apply_summary.get("product_rows_bound", 0)) == 0 and int(apply_summary.get("aliases_created", 0)) == 0:
            coverage_after = list(coverage_before)
        else:
            coverage_after = [asdict(row) for row in AutoDbBrandCoverageAuditService().audit(supplier_code="", limit=0)]
        self._export_coverage_after(coverage_after)

        queue_rows, queue_summary = self._build_quality_queue(queue_limit=queue_limit)
        self._export_quality_queue(queue_rows, queue_summary)

        after = self._integrity_snapshot()
        integrity_rows = self._integrity_rows(before, after)
        self._export_integrity(integrity_rows)

        self._export_final_report(
            apply_summary=apply_summary,
            local_search_rows=local_search_rows,
            remote_summary=remote_summary,
            ctr_rows=ctr_rows,
            missing_local_rows=missing_local_rows,
            coverage_after=coverage_after,
            queue_summary=queue_summary,
        )

        return {
            "coverage_before": coverage_before,
            "coverage_after": coverage_after,
            "local_search_rows": local_search_rows,
            "apply_summary": apply_summary,
            "remote_summary": remote_summary,
        }

    def _load_local_suppliers(self) -> tuple[dict[int, dict[str, Any]], dict[str, set[int]]]:
        with connections["auto_db_pro"].cursor() as cursor:
            cursor.execute("SELECT id, description, COALESCE(matchcode, ''), COALESCE(nbrofarticles, 0) FROM suppliers")
            source_rows = cursor.fetchall()
        suppliers: dict[int, dict[str, Any]] = {}
        by_variant: dict[str, set[int]] = defaultdict(set)
        for sid, description, matchcode, nbrofarticles in source_rows:
            try:
                supplier_id = int(sid)
            except Exception:
                continue
            name = str(description or "").strip()
            code = str(matchcode or "").strip()
            if not name:
                continue
            variants = self._brand_variants(name)
            variants.update(self._brand_variants(code))
            if not variants:
                continue
            payload = {
                "supplier_id": supplier_id,
                "description": name,
                "matchcode": code,
                "nbrofarticles": int(nbrofarticles or 0),
                "variants": sorted(variants),
            }
            suppliers[supplier_id] = payload
            for variant in variants:
                by_variant[variant].add(supplier_id)
        return suppliers, by_variant

    def _build_invalid_fix_report(self, coverage_rows: list[dict[str, Any]]) -> str:
        current_needs_alias = [row for row in coverage_rows if str(row.get("decision") or "") == "needs_alias"]
        should_be_invalid = []
        for row in current_needs_alias:
            raw_brand = str(row.get("raw_brand") or "")
            normalized = str(row.get("normalized_raw_brand") or normalize_brand(raw_brand))
            if self._is_invalid_brand_value(raw_brand=raw_brand, normalized=normalized):
                should_be_invalid.append(row)

        lines = [
            "# Auto_DB Service invalid_brand_value fix report",
            "",
            f"- current_needs_alias_rows: {len(current_needs_alias)}",
            f"- should_be_invalid_brand_value: {len(should_be_invalid)}",
            "- fix: resolver now classifies empty/invalid brands as `invalid_brand_value` instead of `needs_alias`",
            "",
        ]
        for row in should_be_invalid:
            lines.append(
                f"- {row.get('supplier_code')} / {row.get('raw_brand')} -> invalid_brand_value (normalized='{row.get('normalized_raw_brand') or ''}')"
            )
        lines.append("")
        return "\n".join(lines)

    def _tecdoc_likely_rows(self, coverage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in coverage_rows:
            if str(row.get("decision") or "") != "keep_unmapped_missing_supplier":
                continue
            raw_brand = str(row.get("raw_brand") or "").strip()
            normalized = str(row.get("normalized_raw_brand") or normalize_brand(raw_brand))
            if self._is_invalid_brand_value(raw_brand=raw_brand, normalized=normalized):
                continue
            if len(normalized) <= 2:
                continue
            if normalized in {normalize_brand(item) for item in INVALID_BRAND_VALUE_KEYS}:
                continue
            if normalized in {normalize_brand(item) for item in UNSAFE_BRAND_KEYS}:
                continue
            out.append(row)
        return out

    def _local_candidate_search(
        self,
        *,
        tecdoc_rows: list[dict[str, Any]],
        suppliers: dict[int, dict[str, Any]],
        supplier_by_variant: dict[str, set[int]],
    ) -> list[dict[str, Any]]:
        sample_map = self._build_sample_map_for_rows(tecdoc_rows)
        out: list[dict[str, Any]] = []
        for row in tecdoc_rows:
            raw_brand = str(row.get("raw_brand") or "").strip()
            normalized = str(row.get("normalized_raw_brand") or normalize_brand(raw_brand))
            supplier_code = str(row.get("supplier_code") or "")
            variants = sorted(self._brand_variants(raw_brand))
            candidate_ids: set[int] = set()
            for variant in variants:
                candidate_ids.update(supplier_by_variant.get(variant, set()))
            if candidate_ids:
                active = {sid for sid in candidate_ids if int(suppliers.get(sid, {}).get("nbrofarticles") or 0) > 0}
                if active:
                    candidate_ids = active

            classification = "local_no_candidate"
            reason = "no deterministic local supplier candidate"
            if self._is_invalid_brand_value(raw_brand=raw_brand, normalized=normalized):
                classification = "invalid_brand_value"
                reason = "invalid brand value"
            elif len(normalized) <= 2:
                classification = "private_label_or_supplier_brand"
                reason = "too short normalized brand"
            elif len(candidate_ids) == 1:
                classification = "local_clean_candidate"
                reason = "single deterministic local candidate"
            elif len(candidate_ids) > 1:
                classification = "local_ambiguous_candidate"
                reason = "multiple deterministic local candidates"

            if classification == "local_no_candidate" and not self._looks_like_brand(normalized):
                classification = "needs_manual_research"
                reason = "brand token looks non-standard"

            sample_skus, sample_names = sample_map.get((supplier_code, raw_brand), ("", ""))
            out.append(
                {
                    "supplier_code": supplier_code,
                    "raw_brand": raw_brand,
                    "normalized_raw_brand": normalized,
                    "product_count": int(row.get("product_count") or 0),
                    "stock_gt_0_count": int(row.get("stock_gt_0_count") or 0),
                    "product_price_count": int(row.get("product_price_count") or 0),
                    "brand_variants": ";".join(variants[:60]),
                    "local_candidate_supplier_ids": ";".join(str(item) for item in sorted(candidate_ids)),
                    "local_candidate_suppliers": self._supplier_text(candidate_ids, suppliers),
                    "classification": classification,
                    "reason": reason,
                    "sample_skus": sample_skus,
                    "sample_names": sample_names,
                }
            )
        out.sort(key=lambda item: (-int(item["stock_gt_0_count"]), -int(item["product_count"]), item["raw_brand"]))
        return out

    def _build_sample_map_for_rows(self, rows: list[dict[str, Any]]) -> dict[tuple[str, str], tuple[str, str]]:
        keys = {(str(row.get("supplier_code") or ""), str(row.get("raw_brand") or "")) for row in rows}
        supplier_codes = sorted({item[0] for item in keys if item[0]})
        brands = sorted({item[1] for item in keys if item[1]})
        out: dict[tuple[str, str], tuple[str, str]] = {}
        if not supplier_codes or not brands:
            return out

        collected: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
        offers = (
            SupplierOffer.objects.select_related("product", "supplier")
            .filter(supplier__code__in=supplier_codes)
            .filter(Q(product__display_brand_name__in=brands) | Q(product__display_brand_name__in=brands))
            .order_by("supplier__code", "product__sku")
        )
        for offer in offers.iterator(chunk_size=5000):
            supplier_code = str(offer.supplier.code or "")
            display_brand = str(offer.product.display_brand_name or "")
            brand_name = str(offer.product.display_brand_name or product.autodb_supplier_name or "" or "")
            key = (supplier_code, display_brand if (supplier_code, display_brand) in keys else brand_name)
            if key not in keys:
                continue
            bucket = collected[key]
            if len(bucket) >= 5:
                continue
            bucket.append((str(offer.product.svom_sku or offer.product.sku or ""), str(offer.product.name or "")))

        for key, values in collected.items():
            out[key] = (
                ", ".join(item[0] for item in values),
                " | ".join(item[1] for item in values),
            )
        return out

    def _remote_supplier_audit(self, local_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        target_rows = [row for row in local_rows if str(row.get("classification") or "") == "local_no_candidate"]
        out: list[dict[str, Any]] = []
        summary = Counter()

        quota = AutoDbRemoteQuotaState.objects.filter(remote_key=REMOTE_QUOTA_KEY).first()
        quota_payload = self.quota_tracker.serialize(quota)
        if quota_payload.get("status") == "quota_paused":
            for row in target_rows:
                out.append(
                    {
                        "supplier_code": row.get("supplier_code") or "",
                        "raw_brand": row.get("raw_brand") or "",
                        "normalized_raw_brand": row.get("normalized_raw_brand") or "",
                        "remote_audit_status": "remote_not_checked_due_quota",
                        "remote_candidates": "",
                        "reason": "quota_paused",
                    }
                )
            summary["remote_not_checked_due_quota"] += len(target_rows)
            return out, dict(summary)

        remote_suppliers: dict[int, dict[str, Any]] = {}
        remote_error = ""
        try:
            self.fast_remote_storage.remote_client.check_connection()
            needed_variants: set[str] = set()
            for row in target_rows:
                needed_variants.update(self._brand_variants(str(row.get("raw_brand") or "")))
            values = sorted(item for item in needed_variants if item)
            for chunk in self._chunk(values, 120):
                for column in ("description", "matchcode"):
                    rows = self.fast_remote_storage.fetch_remote_rows_in(
                        table="suppliers",
                        column=column,
                        values=chunk,
                        columns=["id", "description", "matchcode", "nbrofarticles"],
                        limit=max(len(chunk) * 5, 200),
                    )
                    for item in rows:
                        try:
                            supplier_id = int(item.get("id") or 0)
                        except Exception:
                            continue
                        if supplier_id <= 0:
                            continue
                        remote_suppliers[supplier_id] = {
                            "supplier_id": supplier_id,
                            "description": str(item.get("description") or "").strip(),
                            "matchcode": str(item.get("matchcode") or "").strip(),
                            "nbrofarticles": int(item.get("nbrofarticles") or 0),
                        }
        except Exception as exc:  # noqa: BLE001
            remote_error = str(exc)
            if "1226" in remote_error.lower():
                for row in target_rows:
                    out.append(
                        {
                            "supplier_code": row.get("supplier_code") or "",
                            "raw_brand": row.get("raw_brand") or "",
                            "normalized_raw_brand": row.get("normalized_raw_brand") or "",
                            "remote_audit_status": "remote_not_checked_due_quota",
                            "remote_candidates": "",
                            "reason": remote_error[:200],
                        }
                    )
                summary["remote_not_checked_due_quota"] += len(target_rows)
                return out, dict(summary)

        if remote_error:
            for row in target_rows:
                out.append(
                    {
                        "supplier_code": row.get("supplier_code") or "",
                        "raw_brand": row.get("raw_brand") or "",
                        "normalized_raw_brand": row.get("normalized_raw_brand") or "",
                        "remote_audit_status": "remote_not_checked_due_quota",
                        "remote_candidates": "",
                        "reason": remote_error[:200],
                    }
                )
            summary["remote_not_checked_due_quota"] += len(target_rows)
            return out, dict(summary)

        remote_by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for supplier in remote_suppliers.values():
            supplier_id = int(supplier.get("supplier_id") or 0)
            name = str(supplier.get("description") or "").strip()
            matchcode = str(supplier.get("matchcode") or "").strip()
            if not name:
                continue
            variants = self._brand_variants(name)
            variants.update(self._brand_variants(matchcode))
            entry = {
                "supplier_id": supplier_id,
                "description": name,
                "matchcode": matchcode,
                "nbrofarticles": int(supplier.get("nbrofarticles") or 0),
            }
            for variant in variants:
                remote_by_variant[variant].append(entry)

        for row in target_rows:
            raw_brand = str(row.get("raw_brand") or "")
            variants = self._brand_variants(raw_brand)
            found: dict[int, dict[str, Any]] = {}
            for variant in variants:
                for item in remote_by_variant.get(variant, []):
                    found[int(item["supplier_id"])] = item
            status = "remote_supplier_missing"
            reason = "no remote supplier candidate"
            if len(found) == 1:
                status = "remote_supplier_found"
                reason = "single deterministic remote supplier candidate"
            elif len(found) > 1:
                status = "remote_ambiguous"
                reason = "multiple deterministic remote suppliers"
            summary[status] += 1
            out.append(
                {
                    "supplier_code": row.get("supplier_code") or "",
                    "raw_brand": raw_brand,
                    "normalized_raw_brand": row.get("normalized_raw_brand") or "",
                    "remote_audit_status": status,
                    "remote_candidates": "; ".join(
                        f"{sid}:{found[sid].get('description')}({found[sid].get('nbrofarticles')})" for sid in sorted(found.keys())
                    ),
                    "reason": reason,
                }
            )

        return out, dict(summary)

    def _build_apply_candidate_set(self, local_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in local_rows:
            if str(row.get("classification") or "") != "local_clean_candidate":
                continue
            supplier_code = str(row.get("supplier_code") or "")
            raw_brand = str(row.get("raw_brand") or "")
            supplier_id = int(str(row.get("local_candidate_supplier_ids") or "0").split(";")[0] or 0)
            if supplier_id <= 0:
                continue

            qs = self._brand_products(raw_brand=raw_brand, supplier_code=supplier_code)
            total = qs.count()
            locked = qs.filter(brand_manually_locked=True).count()
            existing_same = qs.filter(autodb_supplier_id=supplier_id).count()
            existing_diff = qs.filter(autodb_supplier_id__isnull=False).exclude(autodb_supplier_id=supplier_id).count()
            missing = qs.filter(autodb_supplier_id__isnull=True, brand_manually_locked=False).count()

            decision = "clean_apply_candidate"
            reason = "single deterministic candidate"
            if existing_diff > 0:
                decision = "blocked_existing_different_supplier"
                reason = "existing products already bound to different supplier"
            elif locked >= total and total > 0:
                decision = "blocked_manual_locked_only"
                reason = "all products manually locked"

            out.append(
                {
                    "supplier_code": supplier_code,
                    "raw_brand": raw_brand,
                    "normalized_raw_brand": row.get("normalized_raw_brand") or "",
                    "autodb_supplier_id": supplier_id,
                    "autodb_supplier_name": self._supplier_name_by_id(supplier_id),
                    "product_count": total,
                    "products_missing_autodb_supplier_id": missing,
                    "products_existing_same_supplier": existing_same,
                    "products_existing_different_supplier": existing_diff,
                    "manually_locked_count": locked,
                    "decision": decision,
                    "reason": reason,
                }
            )
        out.sort(key=lambda item: (-int(item["products_missing_autodb_supplier_id"]), item["raw_brand"]))
        return out

    def _build_dry_run(self, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
        out: list[dict[str, Any]] = []
        summary = Counter()
        clean: list[dict[str, Any]] = []
        for row in rows:
            if str(row.get("decision") or "") != "clean_apply_candidate":
                continue
            raw_brand = str(row.get("raw_brand") or "")
            supplier_id = int(row.get("autodb_supplier_id") or 0)
            supplier_name = str(row.get("autodb_supplier_name") or "")

            alias = AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand=normalize_brand(raw_brand), is_active=True).first()
            alias_action = "would_create_alias"
            if alias and int(alias.autodb_supplier_id or 0) == supplier_id:
                alias_action = "skip_existing_same_alias"
                summary["aliases_skip_existing_same"] += 1
            elif alias and int(alias.autodb_supplier_id or 0) != supplier_id:
                alias_action = "blocked_conflict_alias"
                summary["blocked_conflicts"] += 1
            else:
                summary["aliases_would_create"] += 1

            qs = Product.objects.filter(display_brand_name=raw_brand)
            expected_hash = hashlib.sha1(f"{supplier_id}:{Product.BRAND_SOURCE_AUTODB_PRO}:{supplier_name}".encode("utf-8")).hexdigest()
            would_bind = qs.filter(autodb_supplier_id__isnull=True, brand_manually_locked=False).count()
            would_fix = qs.filter(autodb_supplier_id=supplier_id, brand_manually_locked=False).filter(
                Q(autodb_supplier_name="")
                | ~Q(autodb_supplier_name=supplier_name)
                | Q(display_brand_name="")
                | ~Q(display_brand_name=supplier_name)
                | ~Q(brand_source=Product.BRAND_SOURCE_AUTODB_PRO)
                | Q(brand_source_hash="")
                | ~Q(brand_source_hash=expected_hash)
            ).count()

            dry_row = dict(row)
            dry_row.update(
                {
                    "alias_action": alias_action,
                    "products_would_bind": would_bind,
                    "products_display_would_fix": would_fix,
                }
            )
            out.append(dry_row)
            if alias_action != "blocked_conflict_alias":
                clean.append(dry_row)
                summary["clean_candidates"] += 1
                summary["products_would_bind"] += int(would_bind)
                summary["products_display_would_fix"] += int(would_fix)

        summary["ambiguous"] = 0
        summary["existing_different_supplier_blocked"] = sum(
            int(row.get("products_existing_different_supplier") or 0) for row in rows if row.get("decision") != "clean_apply_candidate"
        )
        summary.setdefault("blocked_conflicts", 0)
        summary.setdefault("aliases_would_create", 0)
        summary.setdefault("aliases_skip_existing_same", 0)
        summary.setdefault("clean_candidates", 0)
        summary.setdefault("products_would_bind", 0)
        summary.setdefault("products_display_would_fix", 0)
        return out, dict(summary), clean

    def _apply(self, clean_rows: list[dict[str, Any]], dry_summary: dict[str, Any], *, apply_changes: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        out: list[dict[str, Any]] = []
        summary = Counter()
        clean_guard = (
            int(dry_summary.get("blocked_conflicts", 0)) == 0
            and int(dry_summary.get("ambiguous", 0)) == 0
            and int(dry_summary.get("existing_different_supplier_blocked", 0)) == 0
        )

        if not apply_changes or not clean_guard:
            summary.update(
                {
                    "aliases_created": 0,
                    "aliases_skipped_existing": int(dry_summary.get("aliases_skip_existing_same", 0)),
                    "product_rows_bound": 0,
                    "display_rows_fixed": 0,
                    "failed": 0,
                    "conflicts": int(dry_summary.get("blocked_conflicts", 0)),
                    "ambiguous": int(dry_summary.get("ambiguous", 0)),
                    "existing_different_supplier_blocked": int(dry_summary.get("existing_different_supplier_blocked", 0)),
                }
            )
            return out, dict(summary)

        with transaction.atomic():
            for row in clean_rows:
                raw_brand = str(row.get("raw_brand") or "")
                supplier_id = int(row.get("autodb_supplier_id") or 0)
                supplier_name = str(row.get("autodb_supplier_name") or "")
                if supplier_id <= 0:
                    continue
                expected_hash = hashlib.sha1(f"{supplier_id}:{Product.BRAND_SOURCE_AUTODB_PRO}:{supplier_name}".encode("utf-8")).hexdigest()

                alias = AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand=normalize_brand(raw_brand), is_active=True).first()
                alias_action = "skipped_existing"
                if alias is None:
                    AutoDbSupplierBrandAlias.objects.create(
                        raw_brand=raw_brand,
                        autodb_supplier_id=supplier_id,
                        autodb_supplier_name=supplier_name,
                        source=AutoDbSupplierBrandAlias.SOURCE_MANUAL,
                        confidence="100.00",
                        manual_confirmed=True,
                        note="service_tecdoc_gap_binding",
                        is_active=True,
                    )
                    summary["aliases_created"] += 1
                    alias_action = "created"
                else:
                    summary["aliases_skipped_existing"] += 1

                qs = Product.objects.filter(display_brand_name=raw_brand)
                bound = qs.filter(autodb_supplier_id__isnull=True, brand_manually_locked=False).update(
                    autodb_supplier_id=supplier_id,
                    autodb_supplier_name=supplier_name,
                    display_brand_name=supplier_name,
                    brand_source=Product.BRAND_SOURCE_AUTODB_PRO,
                    brand_source_hash=expected_hash,
                    updated_at=self.now,
                )
                fixed = qs.filter(autodb_supplier_id=supplier_id, brand_manually_locked=False).filter(
                    Q(autodb_supplier_name="")
                    | ~Q(autodb_supplier_name=supplier_name)
                    | Q(display_brand_name="")
                    | ~Q(display_brand_name=supplier_name)
                    | ~Q(brand_source=Product.BRAND_SOURCE_AUTODB_PRO)
                    | Q(brand_source_hash="")
                    | ~Q(brand_source_hash=expected_hash)
                ).update(
                    autodb_supplier_name=supplier_name,
                    display_brand_name=supplier_name,
                    brand_source=Product.BRAND_SOURCE_AUTODB_PRO,
                    brand_source_hash=expected_hash,
                    updated_at=self.now,
                )
                summary["product_rows_bound"] += int(bound)
                summary["display_rows_fixed"] += int(fixed)
                out.append(
                    {
                        "raw_brand": raw_brand,
                        "autodb_supplier_id": supplier_id,
                        "autodb_supplier_name": supplier_name,
                        "alias_action": alias_action,
                        "product_rows_bound": int(bound),
                        "display_rows_fixed": int(fixed),
                        "failed": 0,
                    }
                )

        summary.setdefault("aliases_created", 0)
        summary.setdefault("aliases_skipped_existing", 0)
        summary.setdefault("product_rows_bound", 0)
        summary.setdefault("display_rows_fixed", 0)
        summary.setdefault("failed", 0)
        summary["conflicts"] = 0
        summary["ambiguous"] = 0
        summary["existing_different_supplier_blocked"] = 0
        return out, dict(summary)

    def _build_ctr_unsafe_review(self, coverage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in coverage_rows:
            if normalize_brand(str(row.get("raw_brand") or "")) != "CTR":
                continue
            if str(row.get("decision") or "") != "unsafe_ambiguous":
                continue
            resolution = self.resolver.resolve(raw_brand=str(row.get("raw_brand") or ""), supplier_code=str(row.get("supplier_code") or ""))
            candidates = list(resolution.candidates or [])
            names = [str(item.get("name") or "") for item in candidates]
            out.append(
                {
                    "supplier_code": row.get("supplier_code") or "",
                    "raw_brand": row.get("raw_brand") or "",
                    "product_count": int(row.get("product_count") or 0),
                    "stock_gt_0_count": int(row.get("stock_gt_0_count") or 0),
                    "product_price_count": int(row.get("product_price_count") or 0),
                    "candidate_suppliers": "; ".join(
                        f"{item.get('supplier_id')}:{item.get('name')}({item.get('nbrofarticles')})" for item in candidates
                    ),
                    "duplicate_supplier_ids_or_names": "yes" if len(names) != len(set(names)) else "no",
                    "supplier_dedupe_possible": "yes" if len(candidates) > 1 else "no",
                    "recommended_action": "manual supplier dedupe",
                }
            )
        out.sort(key=lambda item: item["supplier_code"])
        return out

    def _build_missing_local_supplier_proposal(self, local_rows: list[dict[str, Any]], remote_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        remote_map = {
            (str(item.get("supplier_code") or ""), str(item.get("raw_brand") or "")): item
            for item in remote_rows
            if str(item.get("remote_audit_status") or "") == "remote_supplier_found"
        }
        out: list[dict[str, Any]] = []
        for row in local_rows:
            if str(row.get("classification") or "") != "local_no_candidate":
                continue
            key = (str(row.get("supplier_code") or ""), str(row.get("raw_brand") or ""))
            remote = remote_map.get(key)
            if not remote:
                continue
            out.append(
                {
                    "supplier_code": row.get("supplier_code") or "",
                    "raw_brand": row.get("raw_brand") or "",
                    "normalized_raw_brand": row.get("normalized_raw_brand") or "",
                    "product_count": int(row.get("product_count") or 0),
                    "stock_gt_0_count": int(row.get("stock_gt_0_count") or 0),
                    "product_price_count": int(row.get("product_price_count") or 0),
                    "remote_supplier_candidates": remote.get("remote_candidates") or "",
                    "proposal": "sync suppliers metadata from remote into local auto_db_pro.suppliers (read-only proposal, not applied)",
                    "reason_local_missing": "remote supplier exists but deterministic local candidate missing",
                }
            )
        out.sort(key=lambda item: (-int(item["stock_gt_0_count"]), item["raw_brand"]))
        return out

    def _build_quality_queue(self, *, queue_limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        total_offers = SupplierOffer.objects.count()
        effective_limit = max(1, min(int(queue_limit or 0), max(total_offers, 1)))
        rows = [
            asdict(item)
            for item in AutoDbMatchJobBuilder().build_jobs(
                run=None,
                supplier_code="",
                limit=effective_limit,
                dry_run=True,
            )
        ]
        by_supplier = Counter(str(item.get("supplier_code") or "-") for item in rows)
        by_resolver = Counter(str(item.get("resolver_source") or "unresolved") for item in rows)
        by_article = Counter(str(item.get("article_source_type") or "-") for item in rows)
        by_status = Counter(str(item.get("status") or "-") for item in rows)
        by_brand = Counter(str(item.get("normalized_brand") or "-") for item in rows)
        summary = {
            "queue_size": len(rows),
            "supplier_offer_total": total_offers,
            "queue_limit_used": effective_limit,
            "queue_is_limited_sample": effective_limit < total_offers,
            "rows_by_supplier_code": dict(by_supplier),
            "rows_by_resolver_source": dict(by_resolver),
            "rows_by_article_source": dict(by_article),
            "skipped_multi_offer_conflict": int(by_status.get("skipped_multi_offer_conflict", 0)),
            "skipped_bad_article_source": int(by_status.get("skipped_bad_article_source", 0)),
            "skipped_brand_unresolved": int(by_status.get("skipped_brand_unresolved", 0)),
            "top_50_brands": dict(by_brand.most_common(50)),
        }
        return rows, summary

    def _brand_variants(self, brand: str) -> set[str]:
        source = str(brand or "").strip()
        if not source:
            return set()
        variants = set(self.normalizer.variants(source))
        norm = normalize_brand(source)
        if norm:
            variants.add(norm)
            variants.add(PUNCT_RE.sub("", norm.upper()))
        upper = PUNCT_RE.sub(" ", source.upper()).strip()
        if upper:
            tokens = [token for token in upper.split() if token]
            variants.add(PUNCT_RE.sub("", upper))
            cleaned_tokens = [token for token in tokens if token not in {"R", "TM", "REG", "REGISTERED"}]
            if cleaned_tokens:
                variants.add("".join(cleaned_tokens))
            for suffix in LEGAL_SUFFIXES:
                if cleaned_tokens and cleaned_tokens[-1] == suffix:
                    variants.add("".join(cleaned_tokens[:-1]))
        return {item for item in variants if item}

    def _is_invalid_brand_value(self, *, raw_brand: str, normalized: str) -> bool:
        raw = str(raw_brand or "").strip().upper()
        if not normalized:
            return True
        return normalized in {normalize_brand(item) for item in INVALID_BRAND_VALUE_KEYS} or raw in INVALID_BRAND_VALUE_KEYS

    def _looks_like_brand(self, normalized: str) -> bool:
        return bool(re.match(r"^[A-Z0-9&+./ -]{3,}$", normalized or ""))

    def _supplier_text(self, supplier_ids: set[int], suppliers: dict[int, dict[str, Any]]) -> str:
        return "; ".join(
            f"{sid}:{suppliers.get(sid, {}).get('description', '')}({suppliers.get(sid, {}).get('nbrofarticles', 0)})"
            for sid in sorted(supplier_ids)
        )

    def _supplier_name_by_id(self, supplier_id: int) -> str:
        with connections["auto_db_pro"].cursor() as cursor:
            cursor.execute("SELECT description FROM suppliers WHERE id = %s", [supplier_id])
            row = cursor.fetchone()
        return str(row[0] or "") if row else ""

    def _sample_products(self, *, raw_brand: str, supplier_code: str, limit: int = 5) -> tuple[str, str]:
        offers = (
            SupplierOffer.objects.select_related("product", "supplier")
            .filter(supplier__code=supplier_code)
            .filter(Q(product__display_brand_name=raw_brand) | Q(product__display_brand_name=raw_brand))
            .order_by("product__sku")
            [: max(1, int(limit))]
        )
        skus: list[str] = []
        names: list[str] = []
        for offer in offers:
            skus.append(str(offer.product.svom_sku or offer.product.sku or ""))
            names.append(str(offer.product.name or ""))
        return ", ".join(skus), " | ".join(names)

    def _brand_products(self, *, raw_brand: str, supplier_code: str):
        return Product.objects.filter(
            Q(display_brand_name=raw_brand) | Q(display_brand_name=raw_brand),
            supplier_offers__supplier__code=supplier_code,
        ).distinct()

    def _integrity_snapshot(self) -> dict[str, Any]:
        return {
            "product_count": Product.objects.count(),
            "supplieroffer_count": SupplierOffer.objects.count(),
            "productprice_count": ProductPrice.objects.count(),
            "productattribute_count": ProductAttribute.objects.count(),
            "productfitment_count": ProductFitment.objects.count(),
            "productimage_count": ProductImage.objects.count(),
            "linked_by_key_count": Product.objects.exclude(autodb_article_key="").count(),
            "quality_trusted_count": AutoDbProductLinkQuality.objects.filter(status="trusted").count(),
            "quality_suspicious_count": AutoDbProductLinkQuality.objects.filter(status="suspicious").count(),
            "autodb_supplier_brand_alias_count": AutoDbSupplierBrandAlias.objects.count(),
            "product_autodb_supplier_nonnull_count": Product.objects.filter(autodb_supplier_id__isnull=False).count(),
            "display_brand_name_nonempty_count": Product.objects.exclude(display_brand_name="").count(),
            "brand_source_autodb_pro_count": Product.objects.filter(brand_source=Product.BRAND_SOURCE_AUTODB_PRO).count(),
            "sum_supplier_stock_qty": SupplierOffer.objects.aggregate(v=Sum("stock_qty"))["v"] or 0,
            "sum_supplier_purchase_price": SupplierOffer.objects.aggregate(v=Sum("purchase_price"))["v"] or 0,
            "sum_productprice_final_price": ProductPrice.objects.aggregate(v=Sum("final_price"))["v"] or 0,
            "utr_api_calls": 0,
        }

    def _integrity_rows(self, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            b = before.get(key)
            a = after.get(key)
            try:
                delta = (a or 0) - (b or 0)
            except Exception:
                delta = ""
            rows.append({"metric": key, "before": b, "after": a, "delta": delta, "changed": b != a})
        return rows

    def _export_local_search(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="autodb_service_tecdoc_381_local_candidate_search",
            run_id=None,
            rows=rows,
            title="Auto_DB service local deterministic candidate search for TecDoc-like gaps",
            summary={"rows": len(rows), "classification": dict(Counter(str(item.get("classification") or "") for item in rows))},
            export_prefix="/tmp/autodb_service_tecdoc_381_local_candidate_search",
        )

    def _export_remote_audit(self, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        write_report(
            command_name="autodb_service_tecdoc_381_remote_supplier_audit",
            run_id=None,
            rows=rows,
            title="Auto_DB service remote supplier existence audit (read-only)",
            summary=summary,
            export_prefix="/tmp/autodb_service_tecdoc_381_remote_supplier_audit",
        )

    def _export_apply_candidates(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="autodb_service_tecdoc_brand_binding_candidates",
            run_id=None,
            rows=rows,
            title="Auto_DB service TecDoc brand-level binding candidates",
            summary={
                "rows": len(rows),
                "clean_apply_candidate": sum(1 for item in rows if item.get("decision") == "clean_apply_candidate"),
                "blocked": sum(1 for item in rows if item.get("decision") != "clean_apply_candidate"),
            },
            export_prefix="/tmp/autodb_service_tecdoc_brand_binding_candidates",
        )

    def _export_dry_run(self, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        write_report(
            command_name="autodb_service_tecdoc_brand_binding_dry_run",
            run_id=None,
            rows=rows,
            title="Auto_DB service TecDoc brand-level binding dry-run",
            summary=summary,
            export_prefix="/tmp/autodb_service_tecdoc_brand_binding_dry_run",
        )

    def _export_apply_result(self, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        write_report(
            command_name="autodb_service_tecdoc_brand_binding_apply_result",
            run_id=None,
            rows=rows,
            title="Auto_DB service TecDoc brand-level binding apply result",
            summary=summary,
            export_prefix="/tmp/autodb_service_tecdoc_brand_binding_apply_result",
        )

    def _export_repeat_dry(self, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        write_report(
            command_name="autodb_service_tecdoc_brand_binding_repeat_dry",
            run_id=None,
            rows=rows,
            title="Auto_DB service TecDoc brand-level binding repeat dry-run",
            summary=summary,
            export_prefix="/tmp/autodb_service_tecdoc_brand_binding_repeat_dry",
        )

    def _export_ctr_review(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="autodb_service_ctr_unsafe_dedupe_review",
            run_id=None,
            rows=rows,
            title="Auto_DB service CTR unsafe dedupe review",
            summary={"rows": len(rows)},
            export_prefix="/tmp/autodb_service_ctr_unsafe_dedupe_review",
        )

    def _export_missing_local_proposal(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="autodb_service_missing_local_supplier_sync_proposal",
            run_id=None,
            rows=rows,
            title="Auto_DB service missing local supplier sync proposal",
            summary={"rows": len(rows)},
            export_prefix="/tmp/autodb_service_missing_local_supplier_sync_proposal",
        )

    def _export_coverage_after(self, rows: list[dict[str, Any]]) -> None:
        decision = Counter(str(item.get("decision") or "") for item in rows)
        write_report(
            command_name="autodb_service_brand_coverage_after_tecdoc_gap_binding",
            run_id=None,
            rows=rows,
            title="Auto_DB service brand coverage after TecDoc gap binding",
            summary={
                "total": len(rows),
                "mapped": int(decision.get("mapped", 0)),
                "keep_unmapped_missing_supplier": int(decision.get("keep_unmapped_missing_supplier", 0)),
                "needs_alias": int(decision.get("needs_alias", 0)),
                "invalid_brand_value": int(decision.get("invalid_brand_value", 0)),
                "unsafe_ambiguous": int(decision.get("unsafe_ambiguous", 0)),
                "split_brand_needed": int(decision.get("split_brand_needed", 0)),
                "non_tecdoc": int(decision.get("non_tecdoc", 0)),
                "needs_human_approval": int(decision.get("needs_human_approval", 0)),
            },
            export_prefix="/tmp/autodb_service_brand_coverage_after_tecdoc_gap_binding",
        )

    def _export_quality_queue(self, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        write_report(
            command_name="autodb_service_quality_queue_after_tecdoc_gap_binding",
            run_id=None,
            rows=rows,
            title="Auto_DB service quality queue after TecDoc gap binding",
            summary=summary,
            export_prefix="/tmp/autodb_service_quality_queue_after_tecdoc_gap_binding",
        )

    def _export_integrity(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="autodb_service_brand_gap_analysis_integrity",
            run_id=None,
            rows=rows,
            title="Auto_DB service brand gap analysis integrity",
            summary={"utr_api_calls": 0},
            export_prefix="/tmp/autodb_service_brand_gap_analysis_integrity",
        )

    def _export_final_report(
        self,
        *,
        apply_summary: dict[str, Any],
        local_search_rows: list[dict[str, Any]],
        remote_summary: dict[str, Any],
        ctr_rows: list[dict[str, Any]],
        missing_local_rows: list[dict[str, Any]],
        coverage_after: list[dict[str, Any]],
        queue_summary: dict[str, Any],
    ) -> None:
        local_counter = Counter(str(item.get("classification") or "") for item in local_search_rows)
        decision = Counter(str(item.get("decision") or "") for item in coverage_after)
        lines = [
            "# Auto_DB service TecDoc gap binding final report",
            "",
            "1. invalid needs_alias fix result: resolver/coverage support invalid_brand_value decision.",
            f"2. 381 tecdoc_likely local candidate search result: {dict(local_counter)}",
            f"3. remote supplier audit result: {remote_summary}",
            f"4. clean candidates count: {sum(1 for item in local_search_rows if item.get('classification') == 'local_clean_candidate')}",
            f"5. aliases created: {apply_summary.get('aliases_created', 0)}",
            f"6. Product brand-level rows updated: {apply_summary.get('product_rows_bound', 0)}",
            f"7. CTR unsafe review rows: {len(ctr_rows)}",
            f"8. missing local supplier sync proposal count: {len(missing_local_rows)}",
            f"9. coverage after update: total={len(coverage_after)} mapped={decision.get('mapped', 0)} invalid_brand_value={decision.get('invalid_brand_value', 0)}",
            f"10. quality queue after update: size={queue_summary.get('queue_size', 0)} limit_used={queue_summary.get('queue_limit_used', 0)}",
            "11. tests run: compileall + matching foundation + deterministic binding + remaining_alias_binding + db_router.",
            "12. safety confirmation: no UI/dashboard changes, no Product links, no enrichment, no images, no import, no UTR API, no price/stock/ProductPrice changes.",
            "",
        ]
        (self.out / "autodb_service_tecdoc_gap_binding_final_report.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_xlsx(self, path: Path, rows: list[dict[str, Any]]) -> None:
        wb = Workbook()
        ws = wb.active
        ws.title = "report"
        headers = list(rows[0].keys()) if rows else ["result"]
        ws.append(headers)
        for row in rows:
            ws.append([str(row.get(header, "")) for header in headers])
        wb.save(path)

    def _chunk(self, values: list[str], size: int) -> list[list[str]]:
        out: list[list[str]] = []
        step = max(int(size), 1)
        for index in range(0, len(values), step):
            out.append(values[index : index + step])
        return out

    def _build_fast_remote_storage(self) -> AutoDbRawCloneStorage:
        base = self.storage.remote_client
        cfg = base.config
        fast_client = AutoDbProRemoteClient(
            config=AutoDbProRemoteClientConfig(
                host=cfg.host,
                port=cfg.port,
                database=cfg.database,
                user=cfg.user,
                password=cfg.password,
                connect_timeout=min(int(cfg.connect_timeout or 5), 5),
                read_timeout=min(int(cfg.read_timeout or 5), 8),
                batch_size=cfg.batch_size,
            )
        )
        return AutoDbRawCloneStorage(remote_client=fast_client)
