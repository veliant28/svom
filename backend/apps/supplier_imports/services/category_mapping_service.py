from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
import re
import unicodedata
from typing import Iterable

from django.db.models import QuerySet
from django.utils import timezone

from apps.catalog.models import Category
from apps.supplier_imports.models import SupplierRawOffer
from .category_mapping_guardrails import CategoryMappingGuardrails, GuardrailHit

_AUTO_CONFIDENCE_THRESHOLD = Decimal("0.900")
_REVIEW_CONFIDENCE_THRESHOLD = Decimal("0.620")
_FORCE_TITLE_SIGNATURE_AUTO_THRESHOLD = Decimal("0.940")

_FORCE_RISKY_REASONS = frozenset(
    {
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TITLE_SIGNATURE,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_BRAND_CLUSTER,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TOKEN_CLUSTER,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_RELAXED_NAME,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_SUPPLIER_DEFAULT,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GLOBAL_DEFAULT,
    }
)

_FORCE_ALWAYS_REVIEW_REASONS = frozenset(
    {
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_BRAND_CLUSTER,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TOKEN_CLUSTER,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_RELAXED_NAME,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_SUPPLIER_DEFAULT,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GLOBAL_DEFAULT,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REMAP,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REVIEW,
    }
)

_SIGNAL_KEYWORDS = (
    "category",
    "group",
    "катег",
    "груп",
    "section",
    "segment",
    "подгруп",
)

_SPLIT_RE = re.compile(r"[>|/\\]+")
_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯіІїЇєЄ0-9]+", flags=re.UNICODE)
_STOP_TOKENS = {
    "для",
    "for",
    "and",
    "the",
    "with",
    "без",
    "комплект",
    "набір",
    "set",
    "kit",
}
_TITLE_SIGNATURE_TOKEN_LIMIT = 5
_TOKEN_SIGNAL_LIMIT = 12


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[\s_]+", " ", text)
    text = re.sub(r"[^\w\s/>\\|.-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(value: str) -> set[str]:
    normalized = _normalize_text(value)
    tokens = {
        token
        for token in _TOKEN_RE.findall(normalized)
        if len(token) >= 3 and token not in _STOP_TOKENS
    }
    return tokens


def _to_confidence(value: float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    decimal_value = Decimal(str(value))
    return decimal_value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CategoryMappingDecision:
    status: str
    reason: str
    category: Category | None
    confidence: Decimal | None


@dataclass(frozen=True)
class CategoryMappingApplyResult:
    status: str
    reason: str
    category_id: str | None
    confidence: Decimal | None
    updated: bool
    skipped_manual: bool = False


@dataclass
class CategoryMappingBulkStats:
    processed: int = 0
    updated: int = 0
    skipped_manual: int = 0
    errors: int = 0
    status_counts: dict[str, int] = field(default_factory=dict)
    unmapped_reason_counts: dict[str, int] = field(default_factory=dict)

    def bump_status(self, status: str) -> None:
        self.status_counts[status] = self.status_counts.get(status, 0) + 1

    def bump_unmapped_reason(self, reason: str) -> None:
        key = reason or SupplierRawOffer.CATEGORY_MAPPING_REASON_NO_CATEGORY_SIGNAL
        self.unmapped_reason_counts[key] = self.unmapped_reason_counts.get(key, 0) + 1


@dataclass(frozen=True)
class _CategoryIndexEntry:
    category: Category
    path: str
    path_normalized: str
    is_leaf: bool
    names_normalized: tuple[str, ...]
    token_pool: frozenset[str]
    primary_tokens: frozenset[str]


class _CategoryIndex:
    def __init__(
        self,
        *,
        entries: tuple[_CategoryIndexEntry, ...],
        by_category_id: dict[str, _CategoryIndexEntry],
        exact_name_lookup: dict[str, tuple[_CategoryIndexEntry, ...]],
        exact_path_lookup: dict[str, tuple[_CategoryIndexEntry, ...]],
        token_lookup: dict[str, tuple[_CategoryIndexEntry, ...]],
    ) -> None:
        self.entries = entries
        self.by_category_id = by_category_id
        self.exact_name_lookup = exact_name_lookup
        self.exact_path_lookup = exact_path_lookup
        self.token_lookup = token_lookup

    @classmethod
    def build(cls) -> _CategoryIndex:
        categories = list(
            Category.objects.filter(is_active=True)
            .only("id", "name", "name_uk", "name_ru", "name_en", "parent_id")
            .order_by("name")
        )
        categories_by_id = {str(item.id): item for item in categories}
        has_children = {str(item.parent_id) for item in categories if item.parent_id}

        entries: list[_CategoryIndexEntry] = []
        exact_name_lookup: dict[str, list[_CategoryIndexEntry]] = {}
        exact_path_lookup: dict[str, list[_CategoryIndexEntry]] = {}
        token_lookup: dict[str, list[_CategoryIndexEntry]] = {}

        for category in categories:
            names = tuple(
                item
                for item in {
                    _normalize_text(category.name),
                    _normalize_text(category.name_uk),
                    _normalize_text(category.name_ru),
                    _normalize_text(category.name_en),
                }
                if item
            )
            path = cls._build_path(category=category, categories_by_id=categories_by_id)
            path_normalized = _normalize_text(path)
            token_pool = set()
            for name in names:
                token_pool.update(_tokenize(name))
            token_pool.update(_tokenize(path_normalized))
            primary_tokens = _tokenize(names[0] if names else path_normalized)
            is_leaf = str(category.id) not in has_children

            entry = _CategoryIndexEntry(
                category=category,
                path=path,
                path_normalized=path_normalized,
                is_leaf=is_leaf,
                names_normalized=names,
                token_pool=frozenset(token_pool),
                primary_tokens=frozenset(primary_tokens),
            )
            entries.append(entry)

            for value in names:
                exact_name_lookup.setdefault(value, []).append(entry)
            if path_normalized:
                exact_path_lookup.setdefault(path_normalized, []).append(entry)

            for token in entry.token_pool:
                token_lookup.setdefault(token, []).append(entry)

        return cls(
            entries=tuple(entries),
            by_category_id={str(item.category.id): item for item in entries},
            exact_name_lookup={key: tuple(value) for key, value in exact_name_lookup.items()},
            exact_path_lookup={key: tuple(value) for key, value in exact_path_lookup.items()},
            token_lookup={key: tuple(value) for key, value in token_lookup.items()},
        )

    @staticmethod
    def _build_path(*, category: Category, categories_by_id: dict[str, Category]) -> str:
        items: list[str] = []
        seen: set[str] = set()
        current: Category | None = category
        while current is not None and str(current.id) not in seen:
            seen.add(str(current.id))
            items.append(current.name_uk or current.name or "")
            if not current.parent_id:
                break
            current = categories_by_id.get(str(current.parent_id))

        items.reverse()
        return " / ".join(item for item in items if item.strip())


@dataclass(frozen=True)
class _KnowledgeChoice:
    entry: _CategoryIndexEntry
    confidence: Decimal


@dataclass(frozen=True)
class _ForcedMappingKnowledge:
    default_choice: _KnowledgeChoice | None
    supplier_choices: dict[str, _KnowledgeChoice]
    supplier_brand_choices: dict[tuple[str, str], _KnowledgeChoice]
    brand_choices: dict[str, _KnowledgeChoice]
    supplier_signal_choices: dict[tuple[str, str], _KnowledgeChoice]
    global_signal_choices: dict[str, _KnowledgeChoice]
    title_signature_choices: dict[tuple[str, str, str], _KnowledgeChoice]
    supplier_title_choices: dict[tuple[str, str], _KnowledgeChoice]
    supplier_token_choices: dict[tuple[str, str], _KnowledgeChoice]
    token_choices: dict[str, _KnowledgeChoice]


class SupplierRawOfferCategoryMappingService:
    def __init__(self) -> None:
        self._index = _CategoryIndex.build()
        self._forced_knowledge = self._build_forced_knowledge()
        self._guardrails = CategoryMappingGuardrails()

    def evaluate_offer(self, *, raw_offer: SupplierRawOffer) -> CategoryMappingDecision:
        matched_product = getattr(raw_offer, "matched_product", None)
        if matched_product is not None and getattr(matched_product, "category_id", None):
            category = matched_product.category
            return CategoryMappingDecision(
                status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
                reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FROM_PRODUCT,
                category=category,
                confidence=Decimal("1.000"),
            )

        supplier_signal_decision = self._evaluate_from_supplier_signals(raw_offer=raw_offer)
        if supplier_signal_decision is not None:
            return supplier_signal_decision

        name_decision = self._evaluate_from_product_name(raw_offer=raw_offer)
        if name_decision is not None:
            return name_decision

        return CategoryMappingDecision(
            status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_NO_CATEGORY_SIGNAL,
            category=None,
            confidence=None,
        )

    def apply_manual_mapping(
        self,
        *,
        raw_offer: SupplierRawOffer,
        category: Category,
        actor=None,
    ) -> CategoryMappingApplyResult:
        next_confidence = Decimal("1.000")
        next_reason = SupplierRawOffer.CATEGORY_MAPPING_REASON_MANUAL
        next_status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED
        next_category_id = str(category.id)

        has_changes = self._has_changes(
            raw_offer=raw_offer,
            category_id=next_category_id,
            status=next_status,
            reason=next_reason,
            confidence=next_confidence,
            mapped_by_id=str(actor.id) if actor else None,
        )
        if has_changes:
            raw_offer.mapped_category = category
            raw_offer.category_mapping_status = next_status
            raw_offer.category_mapping_reason = next_reason
            raw_offer.category_mapping_confidence = next_confidence
            raw_offer.category_mapped_at = timezone.now()
            raw_offer.category_mapped_by = actor
            raw_offer.save(
                update_fields=(
                    "mapped_category",
                    "category_mapping_status",
                    "category_mapping_reason",
                    "category_mapping_confidence",
                    "category_mapped_at",
                    "category_mapped_by",
                    "updated_at",
                )
            )

        return CategoryMappingApplyResult(
            status=next_status,
            reason=next_reason,
            category_id=next_category_id,
            confidence=next_confidence,
            updated=has_changes,
        )

    def clear_mapping(self, *, raw_offer: SupplierRawOffer, actor=None) -> CategoryMappingApplyResult:
        next_status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED
        next_reason = SupplierRawOffer.CATEGORY_MAPPING_REASON_UNSET
        has_changes = self._has_changes(
            raw_offer=raw_offer,
            category_id=None,
            status=next_status,
            reason=next_reason,
            confidence=None,
            mapped_by_id=str(actor.id) if actor else None,
        )

        if has_changes:
            raw_offer.mapped_category = None
            raw_offer.category_mapping_status = next_status
            raw_offer.category_mapping_reason = next_reason
            raw_offer.category_mapping_confidence = None
            raw_offer.category_mapped_at = timezone.now()
            raw_offer.category_mapped_by = actor
            raw_offer.save(
                update_fields=(
                    "mapped_category",
                    "category_mapping_status",
                    "category_mapping_reason",
                    "category_mapping_confidence",
                    "category_mapped_at",
                    "category_mapped_by",
                    "updated_at",
                )
            )

        return CategoryMappingApplyResult(
            status=next_status,
            reason=next_reason,
            category_id=None,
            confidence=None,
            updated=has_changes,
        )

    def apply_auto_mapping(
        self,
        *,
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

        decision = self.evaluate_offer(raw_offer=raw_offer)
        if force_map_all and (decision.category is None or decision.status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED):
            decision = self._evaluate_force_mapping(raw_offer=raw_offer, base_decision=decision)
        decision = self._normalize_forced_decision(raw_offer=raw_offer, decision=decision)
        next_category_id = str(decision.category.id) if decision.category else None

        has_changes = self._has_changes(
            raw_offer=raw_offer,
            category_id=next_category_id,
            status=decision.status,
            reason=decision.reason,
            confidence=decision.confidence,
            mapped_by_id=None,
        )

        if has_changes and not dry_run:
            raw_offer.mapped_category = decision.category
            raw_offer.category_mapping_status = decision.status
            raw_offer.category_mapping_reason = decision.reason
            raw_offer.category_mapping_confidence = decision.confidence
            raw_offer.category_mapped_at = timezone.now()
            raw_offer.category_mapped_by = None
            raw_offer.save(
                update_fields=(
                    "mapped_category",
                    "category_mapping_status",
                    "category_mapping_reason",
                    "category_mapping_confidence",
                    "category_mapped_at",
                    "category_mapped_by",
                    "updated_at",
                )
            )

        return CategoryMappingApplyResult(
            status=decision.status,
            reason=decision.reason,
            category_id=next_category_id,
            confidence=decision.confidence,
            updated=has_changes,
        )

    def recheck_risky_mapping(
        self,
        *,
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
            return self.apply_auto_mapping(
                raw_offer=raw_offer,
                overwrite_manual=False,
                force_map_all=True,
                dry_run=dry_run,
            )

        current_reason = raw_offer.category_mapping_reason or ""
        if current_reason not in _FORCE_RISKY_REASONS:
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
            confidence=_to_confidence(raw_offer.category_mapping_confidence) or Decimal("0.680"),
        )
        reviewed_decision = self._normalize_forced_decision(raw_offer=raw_offer, decision=decision, in_recheck=True)
        if reviewed_decision.category is None:
            reviewed_decision = CategoryMappingDecision(
                status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
                reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REVIEW,
                category=raw_offer.mapped_category,
                confidence=Decimal("0.680"),
            )

        next_category_id = str(reviewed_decision.category.id) if reviewed_decision.category else None
        has_changes = self._has_changes(
            raw_offer=raw_offer,
            category_id=next_category_id,
            status=reviewed_decision.status,
            reason=reviewed_decision.reason,
            confidence=reviewed_decision.confidence,
            mapped_by_id=None,
        )

        if has_changes and not dry_run:
            raw_offer.mapped_category = reviewed_decision.category
            raw_offer.category_mapping_status = reviewed_decision.status
            raw_offer.category_mapping_reason = reviewed_decision.reason
            raw_offer.category_mapping_confidence = reviewed_decision.confidence
            raw_offer.category_mapped_at = timezone.now()
            raw_offer.category_mapped_by = None
            raw_offer.save(
                update_fields=(
                    "mapped_category",
                    "category_mapping_status",
                    "category_mapping_reason",
                    "category_mapping_confidence",
                    "category_mapped_at",
                    "category_mapped_by",
                    "updated_at",
                )
            )

        return CategoryMappingApplyResult(
            status=reviewed_decision.status,
            reason=reviewed_decision.reason,
            category_id=next_category_id,
            confidence=reviewed_decision.confidence,
            updated=has_changes,
        )

    def recheck_guardrail_mapping(
        self,
        *,
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
            return self.apply_auto_mapping(
                raw_offer=raw_offer,
                overwrite_manual=False,
                force_map_all=True,
                dry_run=dry_run,
            )

        current_status = raw_offer.category_mapping_status or SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW
        current_reason = raw_offer.category_mapping_reason or SupplierRawOffer.CATEGORY_MAPPING_REASON_LOW_CONFIDENCE
        current_confidence = _to_confidence(raw_offer.category_mapping_confidence) or Decimal("0.680")
        current_decision = CategoryMappingDecision(
            status=current_status,
            reason=current_reason,
            category=raw_offer.mapped_category,
            confidence=current_confidence,
        )
        adjusted = self._apply_guardrails_to_decision(
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
        has_changes = self._has_changes(
            raw_offer=raw_offer,
            category_id=next_category_id,
            status=adjusted.status,
            reason=adjusted.reason,
            confidence=adjusted.confidence,
            mapped_by_id=None,
        )
        if has_changes and not dry_run:
            raw_offer.mapped_category = adjusted.category
            raw_offer.category_mapping_status = adjusted.status
            raw_offer.category_mapping_reason = adjusted.reason
            raw_offer.category_mapping_confidence = adjusted.confidence
            raw_offer.category_mapped_at = timezone.now()
            raw_offer.category_mapped_by = None
            raw_offer.save(
                update_fields=(
                    "mapped_category",
                    "category_mapping_status",
                    "category_mapping_reason",
                    "category_mapping_confidence",
                    "category_mapped_at",
                    "category_mapped_by",
                    "updated_at",
                )
            )

        return CategoryMappingApplyResult(
            status=adjusted.status,
            reason=adjusted.reason,
            category_id=next_category_id,
            confidence=adjusted.confidence,
            updated=has_changes,
        )

    def bulk_auto_map(
        self,
        *,
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
                result = self.apply_auto_mapping(
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

    def _build_forced_knowledge(self) -> _ForcedMappingKnowledge:
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
            if not category_id or category_id not in self._index.by_category_id:
                continue

            supplier_code = _normalize_text(str(row.get("supplier__code") or ""))
            normalized_brand = _normalize_text(str(row.get("normalized_brand") or ""))
            product_name = str(row.get("product_name") or "")
            raw_payload = row.get("raw_payload") or {}

            global_counter[category_id] += 1
            if supplier_code:
                supplier_counter[supplier_code][category_id] += 1
            if normalized_brand:
                brand_counter[normalized_brand][category_id] += 1
                if supplier_code:
                    supplier_brand_counter[(supplier_code, normalized_brand)][category_id] += 1

            signature = self._build_title_signature(product_name)
            if signature and supplier_code:
                supplier_title_counter[(supplier_code, signature)][category_id] += 1
                if normalized_brand:
                    title_signature_counter[(supplier_code, normalized_brand, signature)][category_id] += 1

            tokens = list(_tokenize(product_name))[:_TOKEN_SIGNAL_LIMIT]
            for token in tokens:
                token_counter[token][category_id] += 1
                if supplier_code:
                    supplier_token_counter[(supplier_code, token)][category_id] += 1

            for signal in self._iter_signal_variants(raw_payload):
                global_signal_counter[signal][category_id] += 1
                if supplier_code:
                    supplier_signal_counter[(supplier_code, signal)][category_id] += 1

        supplier_choices: dict[str, _KnowledgeChoice] = {}
        for supplier_code, counter in supplier_counter.items():
            choice = self._select_choice_from_counter(counter, min_total=20, min_share=0.22, base=0.52, cap=0.74)
            if choice is not None:
                supplier_choices[supplier_code] = choice

        supplier_brand_choices: dict[tuple[str, str], _KnowledgeChoice] = {}
        for key, counter in supplier_brand_counter.items():
            choice = self._select_choice_from_counter(counter, min_total=4, min_share=0.34, base=0.56, cap=0.83)
            if choice is not None:
                supplier_brand_choices[key] = choice

        brand_choices: dict[str, _KnowledgeChoice] = {}
        for normalized_brand, counter in brand_counter.items():
            choice = self._select_choice_from_counter(counter, min_total=25, min_share=0.20, base=0.50, cap=0.72)
            if choice is not None:
                brand_choices[normalized_brand] = choice

        supplier_signal_choices: dict[tuple[str, str], _KnowledgeChoice] = {}
        for key, counter in supplier_signal_counter.items():
            choice = self._select_choice_from_counter(counter, min_total=2, min_share=0.35, base=0.58, cap=0.88)
            if choice is not None:
                supplier_signal_choices[key] = choice

        global_signal_choices: dict[str, _KnowledgeChoice] = {}
        for signal, counter in global_signal_counter.items():
            choice = self._select_choice_from_counter(counter, min_total=6, min_share=0.32, base=0.56, cap=0.84)
            if choice is not None:
                global_signal_choices[signal] = choice

        title_signature_choices: dict[tuple[str, str, str], _KnowledgeChoice] = {}
        for key, counter in title_signature_counter.items():
            choice = self._select_choice_from_counter(counter, min_total=2, min_share=0.45, base=0.60, cap=0.90)
            if choice is not None:
                title_signature_choices[key] = choice

        supplier_title_choices: dict[tuple[str, str], _KnowledgeChoice] = {}
        for key, counter in supplier_title_counter.items():
            choice = self._select_choice_from_counter(counter, min_total=3, min_share=0.40, base=0.58, cap=0.85)
            if choice is not None:
                supplier_title_choices[key] = choice

        supplier_token_choices: dict[tuple[str, str], _KnowledgeChoice] = {}
        for key, counter in supplier_token_counter.items():
            choice = self._select_choice_from_counter(counter, min_total=6, min_share=0.34, base=0.53, cap=0.78)
            if choice is not None:
                supplier_token_choices[key] = choice

        token_choices: dict[str, _KnowledgeChoice] = {}
        for token, counter in token_counter.items():
            choice = self._select_choice_from_counter(counter, min_total=30, min_share=0.26, base=0.50, cap=0.72)
            if choice is not None:
                token_choices[token] = choice

        default_choice = self._select_choice_from_counter(global_counter, min_total=1, min_share=0.0, base=0.50, cap=0.70)
        if default_choice is None:
            fallback_entry = next((item for item in self._index.entries if item.is_leaf), None)
            if fallback_entry is None and self._index.entries:
                fallback_entry = self._index.entries[0]
            if fallback_entry is not None:
                default_choice = _KnowledgeChoice(
                    entry=fallback_entry,
                    confidence=Decimal("0.560"),
                )

        return _ForcedMappingKnowledge(
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

    def _select_choice_from_counter(
        self,
        counter: Counter[str],
        *,
        min_total: int,
        min_share: float,
        base: float,
        cap: float,
    ) -> _KnowledgeChoice | None:
        if not counter:
            return None
        total = sum(counter.values())
        if total < min_total:
            return None

        category_id, top_count = counter.most_common(1)[0]
        share = top_count / max(total, 1)
        if share < min_share:
            return None

        entry = self._index.by_category_id.get(str(category_id))
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
        normalized_confidence = _to_confidence(confidence) or Decimal("0.500")
        return _KnowledgeChoice(entry=entry, confidence=normalized_confidence)

    def _evaluate_force_mapping(
        self,
        *,
        raw_offer: SupplierRawOffer,
        base_decision: CategoryMappingDecision,
    ) -> CategoryMappingDecision:
        if base_decision.category is not None:
            return base_decision

        for strategy in (
            self._force_from_signal_learning,
            self._force_from_title_signature,
            self._force_from_brand_cluster,
            self._force_from_token_cluster,
            self._force_from_relaxed_name,
            self._force_from_supplier_default,
            self._force_from_global_default,
        ):
            decision = strategy(raw_offer=raw_offer)
            if decision is not None and decision.category is not None:
                return decision

        return base_decision

    def _normalize_forced_decision(
        self,
        *,
        raw_offer: SupplierRawOffer,
        decision: CategoryMappingDecision,
        in_recheck: bool = False,
    ) -> CategoryMappingDecision:
        if decision.category is None:
            return decision
        if not (decision.reason or "").startswith("force_"):
            return decision

        adjusted = self._apply_guardrails_to_decision(raw_offer=raw_offer, decision=decision)
        confidence = adjusted.confidence or Decimal("0.680")
        status = adjusted.status

        if (
            adjusted.reason in _FORCE_ALWAYS_REVIEW_REASONS
            and adjusted.status != SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED
        ):
            return CategoryMappingDecision(
                status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
                reason=adjusted.reason,
                category=adjusted.category,
                confidence=min(confidence, Decimal("0.790")),
            )

        if adjusted.reason == SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TITLE_SIGNATURE:
            has_alignment = self._has_title_alignment(raw_offer=raw_offer, category=adjusted.category)
            if not has_alignment:
                return CategoryMappingDecision(
                    status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
                    reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REVIEW,
                    category=adjusted.category,
                    confidence=min(confidence, Decimal("0.820")),
                )
            if confidence < _FORCE_TITLE_SIGNATURE_AUTO_THRESHOLD:
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

    def _apply_guardrails_to_decision(
        self,
        *,
        raw_offer: SupplierRawOffer,
        decision: CategoryMappingDecision,
        allowed_guardrail_codes: set[str] | None = None,
    ) -> CategoryMappingDecision:
        if decision.category is None:
            return decision

        entry = self._index.by_category_id.get(str(decision.category.id))
        category_path = entry.path if entry is not None else decision.category.name
        hit = self._guardrails.evaluate(
            category_name=decision.category.name,
            category_path=category_path,
            product_name=raw_offer.product_name or "",
        )
        if hit is None:
            return decision
        if allowed_guardrail_codes is not None and hit.code not in allowed_guardrail_codes:
            return decision

        replacement = self._find_guardrail_replacement(
            hit=hit,
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

    def _find_guardrail_replacement(
        self,
        *,
        hit: GuardrailHit,
        excluded_category_ids: set[str],
    ) -> Category | None:
        scores: dict[str, float] = defaultdict(float)
        for hint in hit.preferred_tokens:
            for token in _tokenize(hint):
                for entry in self._index.token_lookup.get(token, ()):
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
        best_entry = self._index.by_category_id.get(best_category_id)
        return best_entry.category if best_entry is not None else None

    def _has_title_alignment(self, *, raw_offer: SupplierRawOffer, category: Category | None) -> bool:
        if category is None:
            return False
        product_tokens = _tokenize(raw_offer.product_name or "")
        if not product_tokens:
            return False
        entry = self._index.by_category_id.get(str(category.id))
        if entry is None:
            return False

        overlap_primary = len(product_tokens & entry.primary_tokens)
        if overlap_primary > 0:
            return True

        overlap_pool = len(product_tokens & entry.token_pool)
        return overlap_pool >= 2

    def _force_from_signal_learning(self, *, raw_offer: SupplierRawOffer) -> CategoryMappingDecision | None:
        supplier_code = _normalize_text(getattr(raw_offer.supplier, "code", "") or "")
        best_choice: _KnowledgeChoice | None = None
        for signal in self._iter_signal_variants(raw_offer.raw_payload or {}):
            choice = self._forced_knowledge.supplier_signal_choices.get((supplier_code, signal))
            if choice is None:
                choice = self._forced_knowledge.global_signal_choices.get(signal)
            if choice is None:
                continue
            if best_choice is None or choice.confidence > best_choice.confidence:
                best_choice = choice

        if best_choice is None:
            return None

        return self._decision_from_forced_choice(
            choice=best_choice,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_SIGNAL_LEARNING,
        )

    def _force_from_title_signature(self, *, raw_offer: SupplierRawOffer) -> CategoryMappingDecision | None:
        supplier_code = _normalize_text(getattr(raw_offer.supplier, "code", "") or "")
        normalized_brand = _normalize_text(raw_offer.normalized_brand or raw_offer.brand_name or "")
        signature = self._build_title_signature(raw_offer.product_name or "")
        if not supplier_code or not signature:
            return None

        choice = None
        if normalized_brand:
            choice = self._forced_knowledge.title_signature_choices.get((supplier_code, normalized_brand, signature))
        if choice is None:
            choice = self._forced_knowledge.supplier_title_choices.get((supplier_code, signature))

        if choice is None:
            return None

        return self._decision_from_forced_choice(
            choice=choice,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TITLE_SIGNATURE,
        )

    def _force_from_brand_cluster(self, *, raw_offer: SupplierRawOffer) -> CategoryMappingDecision | None:
        supplier_code = _normalize_text(getattr(raw_offer.supplier, "code", "") or "")
        normalized_brand = _normalize_text(raw_offer.normalized_brand or raw_offer.brand_name or "")
        if not normalized_brand:
            return None

        choice = self._forced_knowledge.supplier_brand_choices.get((supplier_code, normalized_brand))
        if choice is None:
            choice = self._forced_knowledge.brand_choices.get(normalized_brand)
        if choice is None:
            return None

        return self._decision_from_forced_choice(
            choice=choice,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_BRAND_CLUSTER,
        )

    def _force_from_token_cluster(self, *, raw_offer: SupplierRawOffer) -> CategoryMappingDecision | None:
        supplier_code = _normalize_text(getattr(raw_offer.supplier, "code", "") or "")
        tokens = list(_tokenize(raw_offer.product_name or ""))[:_TOKEN_SIGNAL_LIMIT]
        if not tokens:
            return None

        scores: dict[str, float] = defaultdict(float)
        for token in tokens:
            supplier_choice = self._forced_knowledge.supplier_token_choices.get((supplier_code, token))
            if supplier_choice is not None:
                scores[str(supplier_choice.entry.category.id)] += float(supplier_choice.confidence) * 1.0
            global_choice = self._forced_knowledge.token_choices.get(token)
            if global_choice is not None:
                scores[str(global_choice.entry.category.id)] += float(global_choice.confidence) * 0.55

        if not scores:
            return None

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_category_id, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        if best_score <= 0:
            return None

        entry = self._index.by_category_id.get(best_category_id)
        if entry is None:
            return None

        total_score = sum(scores.values())
        share = best_score / max(total_score, 0.0001)
        confidence_value = 0.54 + min(0.30, share * 0.30)
        if second_score > 0 and best_score - second_score <= best_score * 0.10:
            confidence_value = min(confidence_value, 0.68)
        if entry.is_leaf:
            confidence_value += 0.02

        choice = _KnowledgeChoice(
            entry=entry,
            confidence=_to_confidence(min(confidence_value, 0.88)) or Decimal("0.620"),
        )
        return self._decision_from_forced_choice(
            choice=choice,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TOKEN_CLUSTER,
        )

    def _force_from_relaxed_name(self, *, raw_offer: SupplierRawOffer) -> CategoryMappingDecision | None:
        product_tokens = _tokenize(raw_offer.product_name or "")
        if not product_tokens:
            return None

        candidate_entries: dict[str, _CategoryIndexEntry] = {}
        for token in product_tokens:
            for entry in self._index.token_lookup.get(token, ()):
                candidate_entries[str(entry.category.id)] = entry
        if not candidate_entries:
            return None

        scored: list[tuple[_CategoryIndexEntry, float]] = []
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

        choice = _KnowledgeChoice(
            entry=best_entry,
            confidence=_to_confidence(min(confidence_value, 0.82)) or Decimal("0.620"),
        )
        return self._decision_from_forced_choice(
            choice=choice,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_RELAXED_NAME,
        )

    def _force_from_supplier_default(self, *, raw_offer: SupplierRawOffer) -> CategoryMappingDecision | None:
        supplier_code = _normalize_text(getattr(raw_offer.supplier, "code", "") or "")
        if not supplier_code:
            return None
        choice = self._forced_knowledge.supplier_choices.get(supplier_code)
        if choice is None:
            return None
        return self._decision_from_forced_choice(
            choice=choice,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_SUPPLIER_DEFAULT,
            cap_to_review=True,
        )

    def _force_from_global_default(self, *, raw_offer: SupplierRawOffer) -> CategoryMappingDecision | None:
        del raw_offer
        choice = self._forced_knowledge.default_choice
        if choice is None:
            return None
        return self._decision_from_forced_choice(
            choice=choice,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GLOBAL_DEFAULT,
            cap_to_review=True,
        )

    def _decision_from_forced_choice(
        self,
        *,
        choice: _KnowledgeChoice,
        reason: str,
        cap_to_review: bool = False,
    ) -> CategoryMappingDecision:
        confidence = choice.confidence
        if cap_to_review:
            confidence = min(confidence, Decimal("0.680"))

        status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW
        if confidence >= _AUTO_CONFIDENCE_THRESHOLD:
            status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED

        return CategoryMappingDecision(
            status=status,
            reason=reason,
            category=choice.entry.category,
            confidence=confidence,
        )

    def _build_title_signature(self, value: str) -> str:
        normalized = _normalize_text(value)
        if not normalized:
            return ""
        tokens = [token for token in _TOKEN_RE.findall(normalized) if len(token) >= 3 and token not in _STOP_TOKENS]
        if not tokens:
            return ""
        return " ".join(tokens[:_TITLE_SIGNATURE_TOKEN_LIMIT])

    def _iter_signal_variants(self, raw_payload: dict) -> set[str]:
        variants: set[str] = set()
        for signal in self._extract_category_signals(raw_payload):
            normalized_signal = _normalize_text(signal)
            if not normalized_signal:
                continue
            variants.add(normalized_signal)
            split_items = [item.strip() for item in _SPLIT_RE.split(normalized_signal) if item.strip()]
            if split_items:
                variants.add(split_items[-1])
        return variants

    def _evaluate_from_supplier_signals(self, *, raw_offer: SupplierRawOffer) -> CategoryMappingDecision | None:
        signals = self._extract_category_signals(raw_offer.raw_payload or {})
        if not signals:
            return None

        best_entry: _CategoryIndexEntry | None = None
        best_confidence: Decimal | None = None
        best_reason = ""
        saw_ambiguous = False

        for signal in signals:
            normalized_signal = _normalize_text(signal)
            if not normalized_signal:
                continue

            exact_candidates = self._lookup_exact_candidates(normalized_signal=normalized_signal)
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

            fuzzy_candidate = self._lookup_fuzzy_candidate(normalized_signal=normalized_signal)
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

        if best_confidence >= _AUTO_CONFIDENCE_THRESHOLD:
            return CategoryMappingDecision(
                status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
                reason=best_reason,
                category=best_entry.category,
                confidence=best_confidence,
            )

        if best_confidence >= _REVIEW_CONFIDENCE_THRESHOLD:
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

    def _evaluate_from_product_name(self, *, raw_offer: SupplierRawOffer) -> CategoryMappingDecision | None:
        product_tokens = _tokenize(raw_offer.product_name or "")
        if len(product_tokens) < 2:
            return None

        candidate_entries: dict[str, _CategoryIndexEntry] = {}
        for token in product_tokens:
            for entry in self._index.token_lookup.get(token, ()):
                candidate_entries[str(entry.category.id)] = entry
        if not candidate_entries:
            return None

        scored: list[tuple[_CategoryIndexEntry, float]] = []
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
                confidence=_to_confidence(min(best_score, 0.840)),
            )

        confidence = _to_confidence(min(best_score, 0.840))
        if confidence is None or confidence < _REVIEW_CONFIDENCE_THRESHOLD:
            return None

        return CategoryMappingDecision(
            status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
            reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_NAME_TOKENS,
            category=best_entry.category,
            confidence=confidence,
        )

    def _lookup_exact_candidates(self, *, normalized_signal: str) -> tuple[_CategoryIndexEntry, ...]:
        direct = self._index.exact_name_lookup.get(normalized_signal, ())
        if direct:
            return direct

        path = self._index.exact_path_lookup.get(normalized_signal, ())
        if path:
            return path

        if " / " in normalized_signal:
            tail = normalized_signal.rsplit(" / ", 1)[-1].strip()
            return self._index.exact_name_lookup.get(tail, ())

        split_items = [item.strip() for item in _SPLIT_RE.split(normalized_signal) if item.strip()]
        if split_items:
            tail = split_items[-1]
            return self._index.exact_name_lookup.get(tail, ())
        return ()

    def _lookup_fuzzy_candidate(
        self,
        *,
        normalized_signal: str,
    ) -> tuple[_CategoryIndexEntry, Decimal, bool] | None:
        signal_tokens = _tokenize(normalized_signal)
        if not signal_tokens:
            return None

        candidate_entries: dict[str, _CategoryIndexEntry] = {}
        for token in signal_tokens:
            for entry in self._index.token_lookup.get(token, ()):
                candidate_entries[str(entry.category.id)] = entry
        if not candidate_entries:
            return None

        scores: list[tuple[_CategoryIndexEntry, float]] = []
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
        confidence = _to_confidence(min(best_score, 0.890))
        if confidence is None:
            return None
        return best_entry, confidence, ambiguous

    def _extract_category_signals(self, raw_payload: dict) -> list[str]:
        collected: list[str] = []

        def walk(value, *, key_name: str = "") -> None:
            if isinstance(value, dict):
                for key, nested_value in value.items():
                    walk(nested_value, key_name=str(key))
                return

            if isinstance(value, list):
                for item in value:
                    walk(item, key_name=key_name)
                return

            if value is None:
                return

            key_normalized = _normalize_text(key_name)
            if not any(keyword in key_normalized for keyword in _SIGNAL_KEYWORDS):
                return

            text = str(value).strip()
            if not text:
                return
            if len(text) > 255:
                text = text[:255]
            collected.append(text)

        walk(raw_payload)

        unique: list[str] = []
        seen: set[str] = set()
        for item in collected:
            normalized = _normalize_text(item)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(item)
        return unique[:20]

    def _has_changes(
        self,
        *,
        raw_offer: SupplierRawOffer,
        category_id: str | None,
        status: str,
        reason: str,
        confidence: Decimal | None,
        mapped_by_id: str | None,
    ) -> bool:
        current_category_id = str(raw_offer.mapped_category_id) if raw_offer.mapped_category_id else None
        current_confidence = _to_confidence(raw_offer.category_mapping_confidence)
        next_confidence = _to_confidence(confidence)
        current_mapped_by_id = str(raw_offer.category_mapped_by_id) if raw_offer.category_mapped_by_id else None
        return (
            current_category_id != category_id
            or raw_offer.category_mapping_status != status
            or raw_offer.category_mapping_reason != reason
            or current_confidence != next_confidence
            or current_mapped_by_id != mapped_by_id
        )
