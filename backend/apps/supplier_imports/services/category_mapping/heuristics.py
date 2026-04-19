from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from apps.catalog.models import Category
from apps.supplier_imports.models import SupplierRawOffer

from .index import CategoryIndex
from .normalizers import TOKEN_SIGNAL_LIMIT, build_title_signature, iter_signal_variants, normalize_text, tokenize, to_confidence
from .types import (
    AUTO_CONFIDENCE_THRESHOLD,
    CategoryIndexEntry,
    CategoryMappingDecision,
    ForcedMappingKnowledge,
    KnowledgeChoice,
)


def evaluate_force_mapping(
    *,
    raw_offer: SupplierRawOffer,
    base_decision: CategoryMappingDecision,
    index: CategoryIndex,
    forced_knowledge: ForcedMappingKnowledge,
) -> CategoryMappingDecision:
    if base_decision.category is not None:
        return base_decision

    for strategy in (
        force_from_signal_learning,
        force_from_title_signature,
        force_from_brand_cluster,
        force_from_token_cluster,
        force_from_relaxed_name,
        force_from_supplier_default,
        force_from_global_default,
    ):
        decision = strategy(raw_offer=raw_offer, index=index, forced_knowledge=forced_knowledge)
        if decision is not None and decision.category is not None:
            return decision

    return base_decision


def force_from_signal_learning(
    *,
    raw_offer: SupplierRawOffer,
    index: CategoryIndex,
    forced_knowledge: ForcedMappingKnowledge,
) -> CategoryMappingDecision | None:
    del index
    supplier_code = normalize_text(getattr(raw_offer.supplier, "code", "") or "")
    best_choice: KnowledgeChoice | None = None
    for signal in iter_signal_variants(raw_offer.raw_payload or {}):
        choice = forced_knowledge.supplier_signal_choices.get((supplier_code, signal))
        if choice is None:
            choice = forced_knowledge.global_signal_choices.get(signal)
        if choice is None:
            continue
        if best_choice is None or choice.confidence > best_choice.confidence:
            best_choice = choice

    if best_choice is None:
        return None

    return decision_from_forced_choice(
        choice=best_choice,
        reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_SIGNAL_LEARNING,
    )


def force_from_title_signature(
    *,
    raw_offer: SupplierRawOffer,
    index: CategoryIndex,
    forced_knowledge: ForcedMappingKnowledge,
) -> CategoryMappingDecision | None:
    del index
    supplier_code = normalize_text(getattr(raw_offer.supplier, "code", "") or "")
    normalized_brand = normalize_text(raw_offer.normalized_brand or raw_offer.brand_name or "")
    signature = build_title_signature(raw_offer.product_name or "")
    if not supplier_code or not signature:
        return None

    choice = None
    if normalized_brand:
        choice = forced_knowledge.title_signature_choices.get((supplier_code, normalized_brand, signature))
    if choice is None:
        choice = forced_knowledge.supplier_title_choices.get((supplier_code, signature))

    if choice is None:
        return None

    return decision_from_forced_choice(
        choice=choice,
        reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TITLE_SIGNATURE,
    )


def force_from_brand_cluster(
    *,
    raw_offer: SupplierRawOffer,
    index: CategoryIndex,
    forced_knowledge: ForcedMappingKnowledge,
) -> CategoryMappingDecision | None:
    del index
    supplier_code = normalize_text(getattr(raw_offer.supplier, "code", "") or "")
    normalized_brand = normalize_text(raw_offer.normalized_brand or raw_offer.brand_name or "")
    if not normalized_brand:
        return None

    choice = forced_knowledge.supplier_brand_choices.get((supplier_code, normalized_brand))
    if choice is None:
        choice = forced_knowledge.brand_choices.get(normalized_brand)
    if choice is None:
        return None

    return decision_from_forced_choice(
        choice=choice,
        reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_BRAND_CLUSTER,
    )


def force_from_token_cluster(
    *,
    raw_offer: SupplierRawOffer,
    index: CategoryIndex,
    forced_knowledge: ForcedMappingKnowledge,
) -> CategoryMappingDecision | None:
    supplier_code = normalize_text(getattr(raw_offer.supplier, "code", "") or "")
    tokens = list(tokenize(raw_offer.product_name or ""))[:TOKEN_SIGNAL_LIMIT]
    if not tokens:
        return None

    scores: dict[str, float] = defaultdict(float)
    for token in tokens:
        supplier_choice = forced_knowledge.supplier_token_choices.get((supplier_code, token))
        if supplier_choice is not None:
            scores[str(supplier_choice.entry.category.id)] += float(supplier_choice.confidence) * 1.0
        global_choice = forced_knowledge.token_choices.get(token)
        if global_choice is not None:
            scores[str(global_choice.entry.category.id)] += float(global_choice.confidence) * 0.55

    if not scores:
        return None

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_category_id, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    if best_score <= 0:
        return None

    entry = index.by_category_id.get(best_category_id)
    if entry is None:
        return None

    total_score = sum(scores.values())
    share = best_score / max(total_score, 0.0001)
    confidence_value = 0.54 + min(0.30, share * 0.30)
    if second_score > 0 and best_score - second_score <= best_score * 0.10:
        confidence_value = min(confidence_value, 0.68)
    if entry.is_leaf:
        confidence_value += 0.02

    choice = KnowledgeChoice(
        entry=entry,
        confidence=to_confidence(min(confidence_value, 0.88)) or Decimal("0.620"),
    )
    return decision_from_forced_choice(
        choice=choice,
        reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TOKEN_CLUSTER,
    )


def force_from_relaxed_name(
    *,
    raw_offer: SupplierRawOffer,
    index: CategoryIndex,
    forced_knowledge: ForcedMappingKnowledge,
) -> CategoryMappingDecision | None:
    del forced_knowledge
    product_tokens = tokenize(raw_offer.product_name or "")
    if not product_tokens:
        return None

    candidate_entries: dict[str, CategoryIndexEntry] = {}
    for token in product_tokens:
        for entry in index.token_lookup.get(token, ()):  # pragma: no branch
            candidate_entries[str(entry.category.id)] = entry
    if not candidate_entries:
        return None

    scored: list[tuple[CategoryIndexEntry, float]] = []
    for entry in candidate_entries.values():
        overlap_primary = len(product_tokens & entry.primary_tokens)
        overlap_pool = len(product_tokens & entry.token_pool)
        if overlap_pool == 0:
            continue
        primary_ratio = overlap_primary / max(len(entry.primary_tokens), 1)
        product_ratio = overlap_pool / max(len(product_tokens), 1)
        score = (primary_ratio * 0.6) + (product_ratio * 0.4)
        if entry.is_leaf:
            score += 0.04
        if score >= 0.20:
            scored.append((entry, score))

    if not scored:
        return None

    scored.sort(key=lambda item: item[1], reverse=True)
    best_entry, best_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0.0
    confidence_value = 0.50 + min(0.28, best_score * 0.35)
    if second_score > 0 and best_score - second_score <= 0.06:
        confidence_value = min(confidence_value, 0.64)

    choice = KnowledgeChoice(
        entry=best_entry,
        confidence=to_confidence(min(confidence_value, 0.82)) or Decimal("0.620"),
    )
    return decision_from_forced_choice(
        choice=choice,
        reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_RELAXED_NAME,
    )


def force_from_supplier_default(
    *,
    raw_offer: SupplierRawOffer,
    index: CategoryIndex,
    forced_knowledge: ForcedMappingKnowledge,
) -> CategoryMappingDecision | None:
    del index
    supplier_code = normalize_text(getattr(raw_offer.supplier, "code", "") or "")
    if not supplier_code:
        return None
    choice = forced_knowledge.supplier_choices.get(supplier_code)
    if choice is None:
        return None
    return decision_from_forced_choice(
        choice=choice,
        reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_SUPPLIER_DEFAULT,
        cap_to_review=True,
    )


def force_from_global_default(
    *,
    raw_offer: SupplierRawOffer,
    index: CategoryIndex,
    forced_knowledge: ForcedMappingKnowledge,
) -> CategoryMappingDecision | None:
    del raw_offer
    del index
    choice = forced_knowledge.default_choice
    if choice is None:
        return None
    return decision_from_forced_choice(
        choice=choice,
        reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GLOBAL_DEFAULT,
        cap_to_review=True,
    )


def decision_from_forced_choice(
    *,
    choice: KnowledgeChoice,
    reason: str,
    cap_to_review: bool = False,
) -> CategoryMappingDecision:
    confidence = choice.confidence
    if cap_to_review:
        confidence = min(confidence, Decimal("0.680"))

    status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW
    if confidence >= AUTO_CONFIDENCE_THRESHOLD:
        status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED

    return CategoryMappingDecision(
        status=status,
        reason=reason,
        category=choice.entry.category,
        confidence=confidence,
    )


def has_title_alignment(*, raw_offer: SupplierRawOffer, category: Category | None, index: CategoryIndex) -> bool:
    if category is None:
        return False
    product_tokens = tokenize(raw_offer.product_name or "")
    if not product_tokens:
        return False
    entry = index.by_category_id.get(str(category.id))
    if entry is None:
        return False

    overlap_primary = len(product_tokens & entry.primary_tokens)
    if overlap_primary > 0:
        return True

    overlap_pool = len(product_tokens & entry.token_pool)
    return overlap_pool >= 2
