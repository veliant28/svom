from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db.models import QuerySet

from apps.catalog.models import Category
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.services.category_mapping_guardrails import CategoryMappingGuardrails, GuardrailHit

from . import apply as apply_layer
from .forced_knowledge import build_forced_knowledge
from .guardrails import (
    apply_guardrails_to_decision,
    find_guardrail_replacement,
    normalize_forced_decision,
)
from .heuristics import evaluate_force_mapping, has_title_alignment
from .index import CategoryIndex
from .normalizers import build_title_signature, extract_category_signals, iter_signal_variants
from .scoring import (
    evaluate_from_product_name,
    evaluate_from_supplier_signals,
    lookup_exact_candidates,
    lookup_fuzzy_candidate,
)
from .types import CategoryIndexEntry, CategoryMappingApplyResult, CategoryMappingBulkStats, CategoryMappingDecision


class SupplierRawOfferCategoryMappingService:
    def __init__(self) -> None:
        self._index = CategoryIndex.build()
        self._forced_knowledge = build_forced_knowledge(index=self._index)
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
        return apply_layer.apply_manual_mapping(raw_offer=raw_offer, category=category, actor=actor)

    def clear_mapping(self, *, raw_offer: SupplierRawOffer, actor=None) -> CategoryMappingApplyResult:
        return apply_layer.clear_mapping(raw_offer=raw_offer, actor=actor)

    def apply_auto_mapping(
        self,
        *,
        raw_offer: SupplierRawOffer,
        overwrite_manual: bool = False,
        force_map_all: bool = False,
        dry_run: bool = False,
    ) -> CategoryMappingApplyResult:
        return apply_layer.apply_auto_mapping(
            service=self,
            raw_offer=raw_offer,
            overwrite_manual=overwrite_manual,
            force_map_all=force_map_all,
            dry_run=dry_run,
        )

    def recheck_risky_mapping(
        self,
        *,
        raw_offer: SupplierRawOffer,
        dry_run: bool = False,
    ) -> CategoryMappingApplyResult:
        return apply_layer.recheck_risky_mapping(
            service=self,
            raw_offer=raw_offer,
            dry_run=dry_run,
        )

    def recheck_guardrail_mapping(
        self,
        *,
        raw_offer: SupplierRawOffer,
        allowed_guardrail_codes: set[str] | None = None,
        dry_run: bool = False,
    ) -> CategoryMappingApplyResult:
        return apply_layer.recheck_guardrail_mapping(
            service=self,
            raw_offer=raw_offer,
            allowed_guardrail_codes=allowed_guardrail_codes,
            dry_run=dry_run,
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
        return apply_layer.bulk_auto_map(
            service=self,
            queryset=queryset,
            overwrite_manual=overwrite_manual,
            force_map_all=force_map_all,
            dry_run=dry_run,
            chunk_size=chunk_size,
        )

    def _evaluate_from_supplier_signals(self, *, raw_offer: SupplierRawOffer) -> CategoryMappingDecision | None:
        return evaluate_from_supplier_signals(raw_offer=raw_offer, index=self._index)

    def _evaluate_from_product_name(self, *, raw_offer: SupplierRawOffer) -> CategoryMappingDecision | None:
        return evaluate_from_product_name(raw_offer=raw_offer, index=self._index)

    def _evaluate_force_mapping(
        self,
        *,
        raw_offer: SupplierRawOffer,
        base_decision: CategoryMappingDecision,
    ) -> CategoryMappingDecision:
        return evaluate_force_mapping(
            raw_offer=raw_offer,
            base_decision=base_decision,
            index=self._index,
            forced_knowledge=self._forced_knowledge,
        )

    def _normalize_forced_decision(
        self,
        *,
        raw_offer: SupplierRawOffer,
        decision: CategoryMappingDecision,
        in_recheck: bool = False,
    ) -> CategoryMappingDecision:
        return normalize_forced_decision(
            raw_offer=raw_offer,
            decision=decision,
            index=self._index,
            guardrails=self._guardrails,
            in_recheck=in_recheck,
        )

    def _apply_guardrails_to_decision(
        self,
        *,
        raw_offer: SupplierRawOffer,
        decision: CategoryMappingDecision,
        allowed_guardrail_codes: set[str] | None = None,
    ) -> CategoryMappingDecision:
        return apply_guardrails_to_decision(
            raw_offer=raw_offer,
            decision=decision,
            index=self._index,
            guardrails=self._guardrails,
            allowed_guardrail_codes=allowed_guardrail_codes,
        )

    def _find_guardrail_replacement(
        self,
        *,
        hit: GuardrailHit,
        excluded_category_ids: set[str],
    ) -> Category | None:
        return find_guardrail_replacement(
            hit=hit,
            index=self._index,
            excluded_category_ids=excluded_category_ids,
        )

    def _has_title_alignment(self, *, raw_offer: SupplierRawOffer, category: Category | None) -> bool:
        return has_title_alignment(raw_offer=raw_offer, category=category, index=self._index)

    def _build_title_signature(self, value: str) -> str:
        return build_title_signature(value)

    def _iter_signal_variants(self, raw_payload: dict) -> set[str]:
        return iter_signal_variants(raw_payload)

    def _extract_category_signals(self, raw_payload: dict) -> list[str]:
        return extract_category_signals(raw_payload)

    def _lookup_exact_candidates(self, *, normalized_signal: str) -> tuple[CategoryIndexEntry, ...]:
        return lookup_exact_candidates(index=self._index, normalized_signal=normalized_signal)

    def _lookup_fuzzy_candidate(
        self,
        *,
        normalized_signal: str,
    ) -> tuple[CategoryIndexEntry, Decimal, bool] | None:
        return lookup_fuzzy_candidate(index=self._index, normalized_signal=normalized_signal)
