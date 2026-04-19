from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db.models import QuerySet
from django.utils import timezone

from apps.catalog.models import Category
from apps.supplier_imports.models import SupplierRawOffer

from .diagnostics import has_changes
from .normalizers import to_confidence
from .types import (
    FORCE_RISKY_REASONS,
    CategoryMappingApplyResult,
    CategoryMappingBulkStats,
    CategoryMappingDecision,
)

_MAPPING_UPDATE_FIELDS = (
    "mapped_category",
    "category_mapping_status",
    "category_mapping_reason",
    "category_mapping_confidence",
    "category_mapped_at",
    "category_mapped_by",
    "updated_at",
)


def apply_manual_mapping(
    *,
    raw_offer: SupplierRawOffer,
    category: Category,
    actor=None,
) -> CategoryMappingApplyResult:
    next_confidence = Decimal("1.000")
    next_reason = SupplierRawOffer.CATEGORY_MAPPING_REASON_MANUAL
    next_status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED
    next_category_id = str(category.id)

    changed = has_changes(
        raw_offer=raw_offer,
        category_id=next_category_id,
        status=next_status,
        reason=next_reason,
        confidence=next_confidence,
        mapped_by_id=str(actor.id) if actor else None,
    )
    if changed:
        _save_mapping(
            raw_offer=raw_offer,
            category=category,
            status=next_status,
            reason=next_reason,
            confidence=next_confidence,
            actor=actor,
        )

    return CategoryMappingApplyResult(
        status=next_status,
        reason=next_reason,
        category_id=next_category_id,
        confidence=next_confidence,
        updated=changed,
    )


def clear_mapping(*, raw_offer: SupplierRawOffer, actor=None) -> CategoryMappingApplyResult:
    next_status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED
    next_reason = SupplierRawOffer.CATEGORY_MAPPING_REASON_UNSET
    changed = has_changes(
        raw_offer=raw_offer,
        category_id=None,
        status=next_status,
        reason=next_reason,
        confidence=None,
        mapped_by_id=str(actor.id) if actor else None,
    )

    if changed:
        _save_mapping(
            raw_offer=raw_offer,
            category=None,
            status=next_status,
            reason=next_reason,
            confidence=None,
            actor=actor,
        )

    return CategoryMappingApplyResult(
        status=next_status,
        reason=next_reason,
        category_id=None,
        confidence=None,
        updated=changed,
    )


def apply_auto_mapping(
    *,
    service,
    raw_offer: SupplierRawOffer,
    overwrite_manual: bool = False,
    force_map_all: bool = False,
    dry_run: bool = False,
) -> CategoryMappingApplyResult:
    if (
        not overwrite_manual
        and raw_offer.category_mapping_status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED
    ):
        return CategoryMappingApplyResult(
            status=raw_offer.category_mapping_status,
            reason=raw_offer.category_mapping_reason,
            category_id=str(raw_offer.mapped_category_id) if raw_offer.mapped_category_id else None,
            confidence=raw_offer.category_mapping_confidence,
            updated=False,
            skipped_manual=True,
        )

    decision = service.evaluate_offer(raw_offer=raw_offer)
    if force_map_all and (decision.category is None or decision.status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED):
        decision = service._evaluate_force_mapping(raw_offer=raw_offer, base_decision=decision)
    decision = service._normalize_forced_decision(raw_offer=raw_offer, decision=decision)
    next_category_id = str(decision.category.id) if decision.category else None

    changed = has_changes(
        raw_offer=raw_offer,
        category_id=next_category_id,
        status=decision.status,
        reason=decision.reason,
        confidence=decision.confidence,
        mapped_by_id=None,
    )

    if changed and not dry_run:
        _save_mapping(
            raw_offer=raw_offer,
            category=decision.category,
            status=decision.status,
            reason=decision.reason,
            confidence=decision.confidence,
            actor=None,
        )

    return CategoryMappingApplyResult(
        status=decision.status,
        reason=decision.reason,
        category_id=next_category_id,
        confidence=decision.confidence,
        updated=changed,
    )


def recheck_risky_mapping(
    *,
    service,
    raw_offer: SupplierRawOffer,
    dry_run: bool = False,
) -> CategoryMappingApplyResult:
    if raw_offer.category_mapping_status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED:
        return CategoryMappingApplyResult(
            status=raw_offer.category_mapping_status,
            reason=raw_offer.category_mapping_reason,
            category_id=str(raw_offer.mapped_category_id) if raw_offer.mapped_category_id else None,
            confidence=raw_offer.category_mapping_confidence,
            updated=False,
            skipped_manual=True,
        )

    if raw_offer.mapped_category is None:
        return apply_auto_mapping(
            service=service,
            raw_offer=raw_offer,
            overwrite_manual=False,
            force_map_all=True,
            dry_run=dry_run,
        )

    current_reason = raw_offer.category_mapping_reason or ""
    if current_reason not in FORCE_RISKY_REASONS:
        return CategoryMappingApplyResult(
            status=raw_offer.category_mapping_status,
            reason=current_reason,
            category_id=str(raw_offer.mapped_category_id) if raw_offer.mapped_category_id else None,
            confidence=raw_offer.category_mapping_confidence,
            updated=False,
        )

    decision = CategoryMappingDecision(
        status=raw_offer.category_mapping_status or SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
        reason=current_reason,
        category=raw_offer.mapped_category,
        confidence=to_confidence(raw_offer.category_mapping_confidence) or Decimal("0.680"),
    )
    reviewed_decision = service._normalize_forced_decision(raw_offer=raw_offer, decision=decision, in_recheck=True)
    if reviewed_decision.category is None:
        reviewed_decision = CategoryMappingDecision(
            status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REVIEW,
            category=raw_offer.mapped_category,
            confidence=Decimal("0.680"),
        )

    next_category_id = str(reviewed_decision.category.id) if reviewed_decision.category else None
    changed = has_changes(
        raw_offer=raw_offer,
        category_id=next_category_id,
        status=reviewed_decision.status,
        reason=reviewed_decision.reason,
        confidence=reviewed_decision.confidence,
        mapped_by_id=None,
    )

    if changed and not dry_run:
        _save_mapping(
            raw_offer=raw_offer,
            category=reviewed_decision.category,
            status=reviewed_decision.status,
            reason=reviewed_decision.reason,
            confidence=reviewed_decision.confidence,
            actor=None,
        )

    return CategoryMappingApplyResult(
        status=reviewed_decision.status,
        reason=reviewed_decision.reason,
        category_id=next_category_id,
        confidence=reviewed_decision.confidence,
        updated=changed,
    )


def recheck_guardrail_mapping(
    *,
    service,
    raw_offer: SupplierRawOffer,
    allowed_guardrail_codes: set[str] | None = None,
    dry_run: bool = False,
) -> CategoryMappingApplyResult:
    if raw_offer.category_mapping_status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED:
        return CategoryMappingApplyResult(
            status=raw_offer.category_mapping_status,
            reason=raw_offer.category_mapping_reason,
            category_id=str(raw_offer.mapped_category_id) if raw_offer.mapped_category_id else None,
            confidence=raw_offer.category_mapping_confidence,
            updated=False,
            skipped_manual=True,
        )

    if raw_offer.mapped_category is None:
        return apply_auto_mapping(
            service=service,
            raw_offer=raw_offer,
            overwrite_manual=False,
            force_map_all=True,
            dry_run=dry_run,
        )

    current_status = raw_offer.category_mapping_status or SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW
    current_reason = raw_offer.category_mapping_reason or SupplierRawOffer.CATEGORY_MAPPING_REASON_LOW_CONFIDENCE
    current_confidence = to_confidence(raw_offer.category_mapping_confidence) or Decimal("0.680")
    current_decision = CategoryMappingDecision(
        status=current_status,
        reason=current_reason,
        category=raw_offer.mapped_category,
        confidence=current_confidence,
    )
    adjusted = service._apply_guardrails_to_decision(
        raw_offer=raw_offer,
        decision=current_decision,
        allowed_guardrail_codes=allowed_guardrail_codes,
    )

    if (
        adjusted.category == current_decision.category
        and adjusted.reason == current_decision.reason
        and adjusted.status == current_decision.status
        and adjusted.confidence == current_decision.confidence
    ):
        return CategoryMappingApplyResult(
            status=current_decision.status,
            reason=current_decision.reason,
            category_id=str(current_decision.category.id) if current_decision.category else None,
            confidence=current_decision.confidence,
            updated=False,
        )

    next_category_id = str(adjusted.category.id) if adjusted.category else None
    changed = has_changes(
        raw_offer=raw_offer,
        category_id=next_category_id,
        status=adjusted.status,
        reason=adjusted.reason,
        confidence=adjusted.confidence,
        mapped_by_id=None,
    )
    if changed and not dry_run:
        _save_mapping(
            raw_offer=raw_offer,
            category=adjusted.category,
            status=adjusted.status,
            reason=adjusted.reason,
            confidence=adjusted.confidence,
            actor=None,
        )

    return CategoryMappingApplyResult(
        status=adjusted.status,
        reason=adjusted.reason,
        category_id=next_category_id,
        confidence=adjusted.confidence,
        updated=changed,
    )


def bulk_auto_map(
    *,
    service,
    queryset: QuerySet[SupplierRawOffer] | Iterable[SupplierRawOffer],
    overwrite_manual: bool = False,
    force_map_all: bool = False,
    dry_run: bool = False,
    chunk_size: int = 500,
) -> CategoryMappingBulkStats:
    stats = CategoryMappingBulkStats()
    iterator = queryset.iterator(chunk_size=chunk_size) if isinstance(queryset, QuerySet) else queryset

    for raw_offer in iterator:
        stats.processed += 1
        try:
            result = apply_auto_mapping(
                service=service,
                raw_offer=raw_offer,
                overwrite_manual=overwrite_manual,
                force_map_all=force_map_all,
                dry_run=dry_run,
            )
        except Exception:
            stats.errors += 1
            continue

        if result.skipped_manual:
            stats.skipped_manual += 1
        if result.updated:
            stats.updated += 1

        stats.bump_status(result.status)
        if result.status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED:
            stats.bump_unmapped_reason(result.reason)

    return stats


def _save_mapping(
    *,
    raw_offer: SupplierRawOffer,
    category: Category | None,
    status: str,
    reason: str,
    confidence: Decimal | None,
    actor,
) -> None:
    raw_offer.mapped_category = category
    raw_offer.category_mapping_status = status
    raw_offer.category_mapping_reason = reason
    raw_offer.category_mapping_confidence = confidence
    raw_offer.category_mapped_at = timezone.now()
    raw_offer.category_mapped_by = actor
    raw_offer.save(update_fields=_MAPPING_UPDATE_FIELDS)
