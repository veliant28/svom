from __future__ import annotations

from decimal import Decimal

from apps.pricing.services.selector.types import OfferCandidate, OfferStrategy


class OfferSelectionCalculator:
    def sort_candidates(
        self,
        *,
        strategy: str,
        candidates: list[OfferCandidate],
        quantity: int,
    ) -> list[OfferCandidate]:
        if strategy == OfferStrategy.CHEAPEST:
            return sorted(candidates, key=self._cheapest_key)

        if strategy == OfferStrategy.FASTEST_DELIVERY:
            return sorted(candidates, key=self._fastest_key)

        if strategy == OfferStrategy.PREFERRED_SUPPLIER:
            return sorted(candidates, key=self._preferred_key)

        if strategy == OfferStrategy.IN_STOCK_FIRST:
            return sorted(candidates, key=lambda candidate: self._in_stock_first_key(candidate, quantity))

        return sorted(candidates, key=lambda candidate: self._best_offer_key(candidate, quantity))

    def _cheapest_key(self, candidate: OfferCandidate) -> tuple[Decimal, int, int, int, str]:
        return (
            candidate.landed_cost,
            candidate.offer.lead_time_days,
            0 if candidate.has_stock else 1,
            candidate.supplier_priority,
            str(candidate.offer.id),
        )

    def _fastest_key(self, candidate: OfferCandidate) -> tuple[int, Decimal, int, int, str]:
        return (
            candidate.offer.lead_time_days,
            candidate.landed_cost,
            0 if candidate.has_stock else 1,
            candidate.supplier_priority,
            str(candidate.offer.id),
        )

    def _preferred_key(self, candidate: OfferCandidate) -> tuple[int, int, Decimal, int, str]:
        return (
            0 if candidate.supplier_is_preferred else 1,
            0 if candidate.has_stock else 1,
            candidate.landed_cost,
            candidate.offer.lead_time_days,
            str(candidate.offer.id),
        )

    def _in_stock_first_key(self, candidate: OfferCandidate, quantity: int) -> tuple[int, Decimal, int, int, str]:
        if candidate.offer.stock_qty >= quantity:
            stock_bucket = 0
        elif candidate.has_stock:
            stock_bucket = 1
        else:
            stock_bucket = 2

        return (
            stock_bucket,
            candidate.landed_cost,
            candidate.offer.lead_time_days,
            candidate.supplier_priority,
            str(candidate.offer.id),
        )

    def _best_offer_key(self, candidate: OfferCandidate, quantity: int) -> tuple[int, int, int, Decimal, int, float, str]:
        if candidate.offer.stock_qty >= quantity and candidate.offer.lead_time_days <= 1:
            fulfillment_bucket = 0
        elif candidate.offer.stock_qty >= quantity:
            fulfillment_bucket = 1
        elif candidate.has_stock:
            fulfillment_bucket = 2
        else:
            fulfillment_bucket = 3

        return (
            fulfillment_bucket,
            0 if candidate.supplier_is_preferred else 1,
            candidate.supplier_priority,
            candidate.landed_cost,
            candidate.offer.lead_time_days,
            -float(candidate.supplier_quality_score),
            str(candidate.offer.id),
        )
