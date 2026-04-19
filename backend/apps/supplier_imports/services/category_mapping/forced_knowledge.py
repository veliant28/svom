from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

from apps.supplier_imports.models import SupplierRawOffer

from .index import CategoryIndex
from .normalizers import TOKEN_SIGNAL_LIMIT, build_title_signature, iter_signal_variants, normalize_text, tokenize, to_confidence
from .types import ForcedMappingKnowledge, KnowledgeChoice


def build_forced_knowledge(*, index: CategoryIndex) -> ForcedMappingKnowledge:
    global_counter: Counter[str] = Counter()
    supplier_counter: dict[str, Counter[str]] = defaultdict(Counter)
    supplier_brand_counter: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    brand_counter: dict[str, Counter[str]] = defaultdict(Counter)
    supplier_signal_counter: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    global_signal_counter: dict[str, Counter[str]] = defaultdict(Counter)
    title_signature_counter: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    supplier_title_counter: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    supplier_token_counter: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    token_counter: dict[str, Counter[str]] = defaultdict(Counter)

    mapped_rows = (
        SupplierRawOffer.objects.exclude(mapped_category_id__isnull=True)
        .exclude(category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED)
        .values(
            "mapped_category_id",
            "supplier__code",
            "normalized_brand",
            "product_name",
            "raw_payload",
        )
        .iterator(chunk_size=1000)
    )

    for row in mapped_rows:
        category_id = str(row.get("mapped_category_id") or "")
        if not category_id or category_id not in index.by_category_id:
            continue

        supplier_code = normalize_text(str(row.get("supplier__code") or ""))
        normalized_brand = normalize_text(str(row.get("normalized_brand") or ""))
        product_name = str(row.get("product_name") or "")
        raw_payload = row.get("raw_payload") or {}

        global_counter[category_id] += 1
        if supplier_code:
            supplier_counter[supplier_code][category_id] += 1
        if normalized_brand:
            brand_counter[normalized_brand][category_id] += 1
            if supplier_code:
                supplier_brand_counter[(supplier_code, normalized_brand)][category_id] += 1

        signature = build_title_signature(product_name)
        if signature and supplier_code:
            supplier_title_counter[(supplier_code, signature)][category_id] += 1
            if normalized_brand:
                title_signature_counter[(supplier_code, normalized_brand, signature)][category_id] += 1

        tokens = list(tokenize(product_name))[:TOKEN_SIGNAL_LIMIT]
        for token in tokens:
            token_counter[token][category_id] += 1
            if supplier_code:
                supplier_token_counter[(supplier_code, token)][category_id] += 1

        for signal in iter_signal_variants(raw_payload):
            global_signal_counter[signal][category_id] += 1
            if supplier_code:
                supplier_signal_counter[(supplier_code, signal)][category_id] += 1

    supplier_choices: dict[str, KnowledgeChoice] = {}
    for supplier_code, counter in supplier_counter.items():
        choice = select_choice_from_counter(index=index, counter=counter, min_total=20, min_share=0.22, base=0.52, cap=0.74)
        if choice is not None:
            supplier_choices[supplier_code] = choice

    supplier_brand_choices: dict[tuple[str, str], KnowledgeChoice] = {}
    for key, counter in supplier_brand_counter.items():
        choice = select_choice_from_counter(index=index, counter=counter, min_total=4, min_share=0.34, base=0.56, cap=0.83)
        if choice is not None:
            supplier_brand_choices[key] = choice

    brand_choices: dict[str, KnowledgeChoice] = {}
    for normalized_brand, counter in brand_counter.items():
        choice = select_choice_from_counter(index=index, counter=counter, min_total=25, min_share=0.20, base=0.50, cap=0.72)
        if choice is not None:
            brand_choices[normalized_brand] = choice

    supplier_signal_choices: dict[tuple[str, str], KnowledgeChoice] = {}
    for key, counter in supplier_signal_counter.items():
        choice = select_choice_from_counter(index=index, counter=counter, min_total=2, min_share=0.35, base=0.58, cap=0.88)
        if choice is not None:
            supplier_signal_choices[key] = choice

    global_signal_choices: dict[str, KnowledgeChoice] = {}
    for signal, counter in global_signal_counter.items():
        choice = select_choice_from_counter(index=index, counter=counter, min_total=6, min_share=0.32, base=0.56, cap=0.84)
        if choice is not None:
            global_signal_choices[signal] = choice

    title_signature_choices: dict[tuple[str, str, str], KnowledgeChoice] = {}
    for key, counter in title_signature_counter.items():
        choice = select_choice_from_counter(index=index, counter=counter, min_total=2, min_share=0.45, base=0.60, cap=0.90)
        if choice is not None:
            title_signature_choices[key] = choice

    supplier_title_choices: dict[tuple[str, str], KnowledgeChoice] = {}
    for key, counter in supplier_title_counter.items():
        choice = select_choice_from_counter(index=index, counter=counter, min_total=3, min_share=0.40, base=0.58, cap=0.85)
        if choice is not None:
            supplier_title_choices[key] = choice

    supplier_token_choices: dict[tuple[str, str], KnowledgeChoice] = {}
    for key, counter in supplier_token_counter.items():
        choice = select_choice_from_counter(index=index, counter=counter, min_total=6, min_share=0.34, base=0.53, cap=0.78)
        if choice is not None:
            supplier_token_choices[key] = choice

    token_choices: dict[str, KnowledgeChoice] = {}
    for token, counter in token_counter.items():
        choice = select_choice_from_counter(index=index, counter=counter, min_total=30, min_share=0.26, base=0.50, cap=0.72)
        if choice is not None:
            token_choices[token] = choice

    default_choice = select_choice_from_counter(index=index, counter=global_counter, min_total=1, min_share=0.0, base=0.50, cap=0.70)
    if default_choice is None:
        fallback_entry = next((item for item in index.entries if item.is_leaf), None)
        if fallback_entry is None and index.entries:
            fallback_entry = index.entries[0]
        if fallback_entry is not None:
            default_choice = KnowledgeChoice(
                entry=fallback_entry,
                confidence=Decimal("0.560"),
            )

    return ForcedMappingKnowledge(
        default_choice=default_choice,
        supplier_choices=supplier_choices,
        supplier_brand_choices=supplier_brand_choices,
        brand_choices=brand_choices,
        supplier_signal_choices=supplier_signal_choices,
        global_signal_choices=global_signal_choices,
        title_signature_choices=title_signature_choices,
        supplier_title_choices=supplier_title_choices,
        supplier_token_choices=supplier_token_choices,
        token_choices=token_choices,
    )


def select_choice_from_counter(
    *,
    index: CategoryIndex,
    counter: Counter[str],
    min_total: int,
    min_share: float,
    base: float,
    cap: float,
) -> KnowledgeChoice | None:
    if not counter:
        return None
    total = sum(counter.values())
    if total < min_total:
        return None

    category_id, top_count = counter.most_common(1)[0]
    share = top_count / max(total, 1)
    if share < min_share:
        return None

    entry = index.by_category_id.get(str(category_id))
    if entry is None:
        return None

    confidence = base + ((cap - base) * min(share, 1.0))
    if total >= 10:
        confidence += 0.015
    if total >= 50:
        confidence += 0.015
    if entry.is_leaf:
        confidence += 0.02
    confidence = min(confidence, cap + 0.05)
    normalized_confidence = to_confidence(confidence) or Decimal("0.500")
    return KnowledgeChoice(entry=entry, confidence=normalized_confidence)
