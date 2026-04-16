from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count

from apps.supplier_imports.models import ImportRun, ImportRunQuality, SupplierRawOffer


MATCH_RATE_DROP_THRESHOLD = Decimal("15.00")
UNMATCHED_RATE_THRESHOLD = Decimal("20.00")
CONFLICT_RATE_THRESHOLD = Decimal("15.00")
ERROR_RATE_THRESHOLD = Decimal("10.00")


@dataclass(frozen=True)
class QualityComputationResult:
    quality: ImportRunQuality
    flags: list[dict]


class ImportQualityService:
    def refresh_for_run(self, *, run: ImportRun) -> QualityComputationResult:
        quality_mode = self._resolve_quality_mode(run=run)
        if quality_mode == "category_mapping":
            category_counts = self._collect_category_mapping_counts(run=run)
            manual_matched = int(category_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED, 0))
            auto_matched = int(category_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0))
            conflicts = int(category_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0))
            unmatched = int(category_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED, 0))
            matched = manual_matched + auto_matched + conflicts
            ignored = 0

            total_rows = int(run.summary.get("category_total_rows") or 0) if isinstance(run.summary, dict) else 0
            if total_rows <= 0:
                total_rows = max(run.processed_rows, 0)
            if total_rows <= 0:
                total_rows = matched + unmatched + max(run.errors_count, 0)
            status_counts = {
                SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED: manual_matched,
                SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED: auto_matched,
                SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW: conflicts,
                SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED: unmatched,
            }
        else:
            status_counts = self._collect_status_counts(run=run)
            total_rows = max(run.processed_rows, 0)
            if total_rows == 0:
                total_rows = sum(status_counts.values()) + max(run.errors_count, 0)

            auto_matched = status_counts.get(SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED, 0)
            manual_matched = status_counts.get(SupplierRawOffer.MATCH_STATUS_MANUALLY_MATCHED, 0)
            ignored = status_counts.get(SupplierRawOffer.MATCH_STATUS_IGNORED, 0)
            unmatched = status_counts.get(SupplierRawOffer.MATCH_STATUS_UNMATCHED, 0)
            conflicts = status_counts.get(SupplierRawOffer.MATCH_STATUS_MANUAL_REQUIRED, 0)
            matched = auto_matched + manual_matched

        error_rows = max(run.errors_count, 0)
        match_rate = _rate(part=matched, total=total_rows)
        error_rate = _rate(part=error_rows, total=total_rows)

        previous_run = (
            ImportRun.objects.filter(source=run.source)
            .exclude(id=run.id)
            .exclude(status=ImportRun.STATUS_RUNNING)
            .order_by("-created_at")
            .first()
        )
        previous_quality = None
        if previous_run is not None:
            try:
                previous_quality = previous_run.quality
            except ImportRunQuality.DoesNotExist:
                previous_quality = None

        previous_match_rate = previous_quality.match_rate if previous_quality else Decimal("0")
        previous_error_rate = previous_quality.error_rate if previous_quality else Decimal("0")

        match_rate_delta = (match_rate - previous_match_rate).quantize(Decimal("0.01"))
        error_rate_delta = (error_rate - previous_error_rate).quantize(Decimal("0.01"))

        flags = self._build_flags(
            run=run,
            total_rows=total_rows,
            unmatched=unmatched,
            conflicts=conflicts,
            match_rate=match_rate,
            error_rate=error_rate,
            match_rate_delta=match_rate_delta,
        )

        quality, _ = ImportRunQuality.objects.update_or_create(
            run=run,
            defaults={
                "source": run.source,
                "previous_run": previous_run,
                "status": run.status,
                "total_rows": total_rows,
                "matched_rows": matched,
                "auto_matched_rows": auto_matched,
                "manual_matched_rows": manual_matched,
                "ignored_rows": ignored,
                "unmatched_rows": unmatched,
                "conflict_rows": conflicts,
                "error_rows": error_rows,
                "match_rate": match_rate,
                "error_rate": error_rate,
                "match_rate_delta": match_rate_delta,
                "error_rate_delta": error_rate_delta,
                "flags": flags,
                "requires_operator_attention": bool(flags),
                "summary": {
                    "quality_mode": quality_mode,
                    "raw_offer_statuses": status_counts if quality_mode != "category_mapping" else {},
                    "category_mapping_statuses": status_counts if quality_mode == "category_mapping" else {},
                    "previous_run_id": str(previous_run.id) if previous_run else "",
                },
            },
        )
        return QualityComputationResult(quality=quality, flags=flags)

    def compare_with_previous(self, *, run: ImportRun) -> dict:
        result = self.refresh_for_run(run=run)
        quality = result.quality
        previous = None
        if quality.previous_run is not None:
            try:
                previous = quality.previous_run.quality
            except ImportRunQuality.DoesNotExist:
                previous = None

        return {
            "run_id": str(run.id),
            "source_code": run.source.code,
            "current": self._serialize_quality(quality),
            "previous": self._serialize_quality(previous) if previous else None,
            "delta": {
                "match_rate": float(quality.match_rate_delta),
                "error_rate": float(quality.error_rate_delta),
            },
            "flags": quality.flags,
            "requires_operator_attention": quality.requires_operator_attention,
        }

    def _collect_status_counts(self, *, run: ImportRun) -> dict[str, int]:
        buckets = (
            run.raw_offers.values("match_status")
            .annotate(total=Count("id"))
            .order_by("match_status")
        )
        return {item["match_status"]: int(item["total"]) for item in buckets}

    def _collect_category_mapping_counts(self, *, run: ImportRun) -> dict[str, int]:
        summary = run.summary if isinstance(run.summary, dict) else {}
        from_summary = summary.get("category_status_counts")
        if isinstance(from_summary, dict):
            mapped = {str(key): int(value) for key, value in from_summary.items()}
            for status in (
                SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
                SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
                SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
                SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED,
            ):
                mapped.setdefault(status, 0)
            return mapped

        buckets = (
            SupplierRawOffer.objects.filter(source=run.source)
            .values("category_mapping_status")
            .annotate(total=Count("id"))
            .order_by("category_mapping_status")
        )
        mapped = {item["category_mapping_status"]: int(item["total"]) for item in buckets}
        for status in (
            SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
            SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
            SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
            SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED,
        ):
            mapped.setdefault(status, 0)
        return mapped

    def _resolve_quality_mode(self, *, run: ImportRun) -> str:
        summary = run.summary if isinstance(run.summary, dict) else {}
        mode = str(summary.get("quality_mode") or "").strip().lower()
        if mode == "category_mapping":
            return mode
        return "matching"

    def _build_flags(
        self,
        *,
        run: ImportRun,
        total_rows: int,
        unmatched: int,
        conflicts: int,
        match_rate: Decimal,
        error_rate: Decimal,
        match_rate_delta: Decimal,
    ) -> list[dict]:
        flags: list[dict] = []

        if run.status == ImportRun.STATUS_FAILED:
            flags.append(
                {
                    "code": "import_failed",
                    "level": "critical",
                    "message": "Import run failed.",
                }
            )

        if match_rate_delta <= -MATCH_RATE_DROP_THRESHOLD:
            flags.append(
                {
                    "code": "match_rate_drop",
                    "level": "warning",
                    "message": "Match rate dropped significantly compared to previous run.",
                    "value": float(match_rate_delta),
                    "threshold": float(-MATCH_RATE_DROP_THRESHOLD),
                }
            )

        unmatched_rate = _rate(part=unmatched, total=total_rows)
        if unmatched_rate >= UNMATCHED_RATE_THRESHOLD:
            flags.append(
                {
                    "code": "high_unmatched",
                    "level": "warning",
                    "message": "Unmatched rows are above threshold.",
                    "value": float(unmatched_rate),
                    "threshold": float(UNMATCHED_RATE_THRESHOLD),
                }
            )

        conflict_rate = _rate(part=conflicts, total=total_rows)
        if conflict_rate >= CONFLICT_RATE_THRESHOLD:
            flags.append(
                {
                    "code": "high_conflicts",
                    "level": "warning",
                    "message": "Conflict rows are above threshold.",
                    "value": float(conflict_rate),
                    "threshold": float(CONFLICT_RATE_THRESHOLD),
                }
            )

        if error_rate >= ERROR_RATE_THRESHOLD:
            flags.append(
                {
                    "code": "error_rate_high",
                    "level": "critical",
                    "message": "Error rate is above threshold.",
                    "value": float(error_rate),
                    "threshold": float(ERROR_RATE_THRESHOLD),
                }
            )

        return flags

    def _serialize_quality(self, quality: ImportRunQuality | None) -> dict | None:
        if quality is None:
            return None

        return {
            "run_id": str(quality.run_id),
            "status": quality.status,
            "total_rows": quality.total_rows,
            "matched_rows": quality.matched_rows,
            "auto_matched_rows": quality.auto_matched_rows,
            "manual_matched_rows": quality.manual_matched_rows,
            "ignored_rows": quality.ignored_rows,
            "unmatched_rows": quality.unmatched_rows,
            "conflict_rows": quality.conflict_rows,
            "error_rows": quality.error_rows,
            "match_rate": float(quality.match_rate),
            "error_rate": float(quality.error_rate),
            "match_rate_delta": float(quality.match_rate_delta),
            "error_rate_delta": float(quality.error_rate_delta),
            "flags": quality.flags,
            "requires_operator_attention": quality.requires_operator_attention,
            "created_at": quality.created_at,
            "updated_at": quality.updated_at,
        }


def _rate(*, part: int, total: int) -> Decimal:
    if total <= 0:
        return Decimal("0.00")
    value = (Decimal(part) / Decimal(total)) * Decimal("100")
    return value.quantize(Decimal("0.01"))
