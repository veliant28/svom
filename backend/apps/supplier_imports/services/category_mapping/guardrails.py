from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from apps.catalog.models import Category
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.services.category_mapping_guardrails import CategoryMappingGuardrails, GuardrailHit

from .heuristics import has_title_alignment
from .index import CategoryIndex
from .normalizers import tokenize
from .types import (
    FORCE_ALWAYS_REVIEW_REASONS,
    FORCE_TITLE_SIGNATURE_AUTO_THRESHOLD,
    CategoryMappingDecision,
)


def normalize_forced_decision(
    *,
    raw_offer: SupplierRawOffer,
    decision: CategoryMappingDecision,
    index: CategoryIndex,
    guardrails: CategoryMappingGuardrails,
    in_recheck: bool = False,
) -> CategoryMappingDecision:
    if decision.category is None:
        return decision
    if not (decision.reason or "").startswith("force_"):
        return decision

    adjusted = apply_guardrails_to_decision(
        raw_offer=raw_offer,
        decision=decision,
        index=index,
        guardrails=guardrails,
    )
    confidence = adjusted.confidence or Decimal("0.680")
    status = adjusted.status

    if (
        adjusted.reason in FORCE_ALWAYS_REVIEW_REASONS
        and adjusted.status != SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED
    ):
        return CategoryMappingDecision(
            status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
            reason=adjusted.reason,
            category=adjusted.category,
            confidence=min(confidence, Decimal("0.790")),
        )

    if adjusted.reason == SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TITLE_SIGNATURE:
        has_alignment = has_title_alignment(raw_offer=raw_offer, category=adjusted.category, index=index)
        if not has_alignment:
            return CategoryMappingDecision(
                status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
                reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REVIEW,
                category=adjusted.category,
                confidence=min(confidence, Decimal("0.820")),
            )
        if confidence < FORCE_TITLE_SIGNATURE_AUTO_THRESHOLD:
            status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW
        elif in_recheck and confidence < Decimal("0.970"):
            status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW

    if adjusted.reason == SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_SIGNAL_LEARNING and confidence < Decimal("0.920"):
        status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW

    return CategoryMappingDecision(
        status=status,
        reason=adjusted.reason,
        category=adjusted.category,
        confidence=confidence,
    )


def apply_guardrails_to_decision(
    *,
    raw_offer: SupplierRawOffer,
    decision: CategoryMappingDecision,
    index: CategoryIndex,
    guardrails: CategoryMappingGuardrails,
    allowed_guardrail_codes: set[str] | None = None,
) -> CategoryMappingDecision:
    if decision.category is None:
        return decision

    entry = index.by_category_id.get(str(decision.category.id))
    category_path = entry.path if entry is not None else decision.category.name
    hit = guardrails.evaluate(
        category_name=decision.category.name,
        category_path=category_path,
        product_name=raw_offer.product_name or "",
    )
    if hit is None:
        return decision
    if allowed_guardrail_codes is not None and hit.code not in allowed_guardrail_codes:
        return decision

    replacement = find_guardrail_replacement(
        hit=hit,
        index=index,
        excluded_category_ids={str(decision.category.id)},
    )
    if replacement is not None:
        if hit.prefer_auto_status:
            preferred_confidence = hit.remap_min_confidence or Decimal("0.930")
            next_confidence = decision.confidence or preferred_confidence
            next_confidence = min(max(next_confidence, preferred_confidence), Decimal("0.980"))
            return CategoryMappingDecision(
                status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
                reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REMAP,
                category=replacement,
                confidence=next_confidence,
            )
        return CategoryMappingDecision(
            status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REMAP,
            category=replacement,
            confidence=min(decision.confidence or Decimal("0.700"), Decimal("0.780")),
        )

    return CategoryMappingDecision(
        status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
        reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REVIEW,
        category=decision.category,
        confidence=min(decision.confidence or Decimal("0.680"), Decimal("0.760")),
    )


def find_guardrail_replacement(
    *,
    hit: GuardrailHit,
    index: CategoryIndex,
    excluded_category_ids: set[str],
) -> Category | None:
    scores: dict[str, float] = defaultdict(float)
    for hint in hit.preferred_tokens:
        for token in tokenize(hint):
            for entry in index.token_lookup.get(token, ()):  # pragma: no branch
                category_id = str(entry.category.id)
                if category_id in excluded_category_ids:
                    continue
                score = 1.0
                if token in entry.primary_tokens:
                    score += 1.2
                if entry.is_leaf:
                    score += 0.15
                scores[category_id] += score

    if not scores:
        return None
    best_category_id, _ = max(scores.items(), key=lambda item: item[1])
    best_entry = index.by_category_id.get(best_category_id)
    return best_entry.category if best_entry is not None else None
