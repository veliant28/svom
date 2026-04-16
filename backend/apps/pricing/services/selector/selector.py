from __future__ import annotations

from decimal import Decimal

from apps.catalog.models import Product
from apps.pricing.models import SupplierOffer
from apps.pricing.services.rounding import quantize_money
from apps.pricing.services.selector.calculator import OfferSelectionCalculator
from apps.pricing.services.selector.types import OfferCandidate, OfferSelectionResult, OfferStrategy


class SupplierOfferSelector:
    DEFAULT_FALLBACK_CHAIN = (
        OfferStrategy.IN_STOCK_FIRST,
        OfferStrategy.PREFERRED_SUPPLIER,
        OfferStrategy.CHEAPEST,
        OfferStrategy.FASTEST_DELIVERY,
    )

    STRATEGY_REASON = {
        OfferStrategy.BEST_OFFER: "Balanced best-offer strategy (stock, lead time, preferred supplier, landed cost).",
        OfferStrategy.CHEAPEST: "Cheapest strategy selected the lowest landed cost.",
        OfferStrategy.FASTEST_DELIVERY: "Fastest-delivery strategy selected the lowest lead time.",
        OfferStrategy.PREFERRED_SUPPLIER: "Preferred-supplier strategy prioritized preferred suppliers before cost.",
        OfferStrategy.IN_STOCK_FIRST: "In-stock-first strategy prioritized immediate fulfillment before cost.",
    }

    def __init__(self) -> None:
        self.calculator = OfferSelectionCalculator()

    def select_for_product(
        self,
        *,
        product: Product,
        quantity: int = 1,
        strategy: str = OfferStrategy.BEST_OFFER,
    ) -> OfferSelectionResult:
        requested_strategy = strategy if strategy in OfferStrategy.ALL else OfferStrategy.BEST_OFFER
        candidates = self._load_candidates(product)
        attempts = self._build_attempt_chain(requested_strategy)

        for attempt in attempts:
            strategy_candidates = self._filter_candidates_for_strategy(
                candidates=candidates,
                strategy=attempt,
                quantity=max(quantity, 1),
            )
            ordered = self.calculator.sort_candidates(
                strategy=attempt,
                candidates=strategy_candidates,
                quantity=max(quantity, 1),
            )
            candidate = ordered[0] if ordered else None
            if candidate is None:
                continue

            fallback_used = attempt != requested_strategy
            debug_candidates = [item.to_debug_payload() for item in ordered[:8]]

            return OfferSelectionResult(
                selected_offer=candidate.offer,
                requested_strategy=requested_strategy,
                strategy_applied=attempt,
                fallback_used=fallback_used,
                reason=self.STRATEGY_REASON.get(attempt, "Offer strategy selected an available supplier offer."),
                explainability={
                    "requested_strategy": requested_strategy,
                    "strategy_applied": attempt,
                    "fallback_used": fallback_used,
                    "attempt_chain": attempts,
                    "candidates_considered": len(strategy_candidates),
                    "ordered_candidates": debug_candidates,
                },
            )

        return OfferSelectionResult(
            selected_offer=None,
            requested_strategy=requested_strategy,
            strategy_applied=None,
            fallback_used=False,
            reason="No valid supplier offer found for this product.",
            explainability={
                "requested_strategy": requested_strategy,
                "strategy_applied": None,
                "fallback_used": False,
                "attempt_chain": attempts,
                "candidates_considered": 0,
                "ordered_candidates": [],
            },
        )

    def _filter_candidates_for_strategy(
        self,
        *,
        candidates: list[OfferCandidate],
        strategy: str,
        quantity: int,
    ) -> list[OfferCandidate]:
        if strategy == OfferStrategy.PREFERRED_SUPPLIER:
            preferred = [candidate for candidate in candidates if candidate.supplier_is_preferred]
            return preferred

        if strategy == OfferStrategy.IN_STOCK_FIRST:
            in_stock = [candidate for candidate in candidates if candidate.offer.stock_qty >= quantity]
            if in_stock:
                return in_stock

            positive_stock = [candidate for candidate in candidates if candidate.has_stock]
            return positive_stock

        return candidates

    def _build_attempt_chain(self, requested_strategy: str) -> list[str]:
        chain: list[str] = [requested_strategy]
        for fallback in self.DEFAULT_FALLBACK_CHAIN:
            if fallback not in chain:
                chain.append(fallback)
        return chain

    def _load_candidates(self, product: Product) -> list[OfferCandidate]:
        offers = self._load_product_offers(product)
        candidates: list[OfferCandidate] = []

        for offer in offers:
            if not offer.is_available:
                continue
            if offer.purchase_price <= Decimal("0"):
                continue

            landed_cost = quantize_money(offer.purchase_price + offer.logistics_cost + offer.extra_cost)
            quality_score = offer.supplier.quality_score if offer.supplier.quality_score is not None else Decimal("1")
            candidates.append(
                OfferCandidate(
                    offer=offer,
                    landed_cost=landed_cost,
                    has_stock=offer.stock_qty > 0,
                    supplier_is_preferred=offer.supplier.is_preferred,
                    supplier_priority=offer.supplier.priority,
                    supplier_quality_score=quality_score,
                )
            )

        return candidates

    def _load_product_offers(self, product: Product) -> list[SupplierOffer]:
        prefetched = getattr(product, "_prefetched_objects_cache", {})
        prefetched_offers = prefetched.get("supplier_offers")
        if prefetched_offers is not None:
            return list(prefetched_offers)

        return list(
            SupplierOffer.objects.filter(product=product)
            .select_related("supplier")
            .order_by("supplier__priority", "supplier__name", "id")
        )
