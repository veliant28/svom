from __future__ import annotations

from decimal import Decimal

from apps.supplier_imports.models import SupplierRawOffer

from .index import CategoryIndex
from .normalizers import SPLIT_RE, extract_category_signals, normalize_text, tokenize, to_confidence
from .types import AUTO_CONFIDENCE_THRESHOLD, REVIEW_CONFIDENCE_THRESHOLD, CategoryIndexEntry, CategoryMappingDecision


def evaluate_from_supplier_signals(*, raw_offer: SupplierRawOffer, index: CategoryIndex) -> CategoryMappingDecision | None:
    signals = extract_category_signals(raw_offer.raw_payload or {})
    if not signals:
        return None

    best_entry: CategoryIndexEntry | None = None
    best_confidence: Decimal | None = None
    best_reason = ""
    saw_ambiguous = False

    for signal in signals:
        normalized_signal = normalize_text(signal)
        if not normalized_signal:
            continue

        exact_candidates = lookup_exact_candidates(index=index, normalized_signal=normalized_signal)
        if len(exact_candidates) == 1:
            candidate = exact_candidates[0]
            confidence = Decimal("0.960")
            if candidate.is_leaf:
                confidence = Decimal("0.980")
            if best_confidence is None or confidence > best_confidence:
                best_entry = candidate
                best_confidence = confidence
                best_reason = SupplierRawOffer.CATEGORY_MAPPING_REASON_SUPPLIER_CATEGORY_EXACT
            continue

        if len(exact_candidates) > 1:
            saw_ambiguous = True
            continue

        fuzzy_candidate = lookup_fuzzy_candidate(index=index, normalized_signal=normalized_signal)
        if fuzzy_candidate is None:
            continue

        candidate, confidence, ambiguous = fuzzy_candidate
        if ambiguous:
            saw_ambiguous = True
            continue

        if best_confidence is None or confidence > best_confidence:
            best_entry = candidate
            best_confidence = confidence
            best_reason = SupplierRawOffer.CATEGORY_MAPPING_REASON_SUPPLIER_CATEGORY_FUZZY

    if best_entry is None and saw_ambiguous:
        return CategoryMappingDecision(
            status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_AMBIGUOUS_CATEGORY_SIGNAL,
            category=None,
            confidence=None,
        )

    if best_entry is None:
        return None

    if best_confidence is None:
        return None

    if best_confidence >= AUTO_CONFIDENCE_THRESHOLD:
        return CategoryMappingDecision(
            status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
            reason=best_reason,
            category=best_entry.category,
            confidence=best_confidence,
        )

    if best_confidence >= REVIEW_CONFIDENCE_THRESHOLD:
        return CategoryMappingDecision(
            status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_LOW_CONFIDENCE,
            category=best_entry.category,
            confidence=best_confidence,
        )

    return CategoryMappingDecision(
        status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED,
        reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_LOW_CONFIDENCE,
        category=None,
        confidence=best_confidence,
    )


def evaluate_from_product_name(*, raw_offer: SupplierRawOffer, index: CategoryIndex) -> CategoryMappingDecision | None:
    product_tokens = tokenize(raw_offer.product_name or "")
    if len(product_tokens) < 2:
        return None

    candidate_entries: dict[str, CategoryIndexEntry] = {}
    for token in product_tokens:
        for entry in index.token_lookup.get(token, ()):  # pragma: no branch
            candidate_entries[str(entry.category.id)] = entry
    if not candidate_entries:
        return None

    scored: list[tuple[CategoryIndexEntry, float]] = []
    for entry in candidate_entries.values():
        if not entry.primary_tokens:
            continue
        overlap = len(product_tokens & entry.primary_tokens)
        if overlap == 0:
            continue
        coverage = overlap / max(len(entry.primary_tokens), 1)
        if coverage < 0.7:
            continue
        score = (coverage * 0.9) + (0.1 if entry.is_leaf else 0.0)
        scored.append((entry, score))

    if not scored:
        return None

    scored.sort(key=lambda item: item[1], reverse=True)
    best_entry, best_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0.0

    if second_score > 0 and best_score - second_score <= 0.06:
        return CategoryMappingDecision(
            status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_AMBIGUOUS_NAME_SIGNAL,
            category=None,
            confidence=to_confidence(min(best_score, 0.840)),
        )

    confidence = to_confidence(min(best_score, 0.840))
    if confidence is None or confidence < REVIEW_CONFIDENCE_THRESHOLD:
        return None

    return CategoryMappingDecision(
        status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
        reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_NAME_TOKENS,
        category=best_entry.category,
        confidence=confidence,
    )


def lookup_exact_candidates(*, index: CategoryIndex, normalized_signal: str) -> tuple[CategoryIndexEntry, ...]:
    direct = index.exact_name_lookup.get(normalized_signal, ())
    if direct:
        return direct

    path = index.exact_path_lookup.get(normalized_signal, ())
    if path:
        return path

    if " / " in normalized_signal:
        tail = normalized_signal.rsplit(" / ", 1)[-1].strip()
        return index.exact_name_lookup.get(tail, ())

    split_items = [item.strip() for item in SPLIT_RE.split(normalized_signal) if item.strip()]
    if split_items:
        tail = split_items[-1]
        return index.exact_name_lookup.get(tail, ())
    return ()


def lookup_fuzzy_candidate(
    *,
    index: CategoryIndex,
    normalized_signal: str,
) -> tuple[CategoryIndexEntry, Decimal, bool] | None:
    signal_tokens = tokenize(normalized_signal)
    if not signal_tokens:
        return None

    candidate_entries: dict[str, CategoryIndexEntry] = {}
    for token in signal_tokens:
        for entry in index.token_lookup.get(token, ()):  # pragma: no branch
            candidate_entries[str(entry.category.id)] = entry
    if not candidate_entries:
        return None

    scores: list[tuple[CategoryIndexEntry, float]] = []
    for entry in candidate_entries.values():
        overlap = len(signal_tokens & entry.token_pool)
        if overlap == 0:
            continue
        signal_coverage = overlap / len(signal_tokens)
        category_coverage = overlap / max(len(entry.primary_tokens or entry.token_pool), 1)
        score = (signal_coverage * 0.7) + (category_coverage * 0.3)
        if entry.is_leaf:
            score += 0.03
        if score >= 0.55:
            scores.append((entry, score))

    if not scores:
        return None

    scores.sort(key=lambda item: item[1], reverse=True)
    best_entry, best_score = scores[0]
    second_score = scores[1][1] if len(scores) > 1 else 0.0
    ambiguous = second_score > 0 and (best_score - second_score) <= 0.08
    confidence = to_confidence(min(best_score, 0.890))
    if confidence is None:
        return None
    return best_entry, confidence, ambiguous
