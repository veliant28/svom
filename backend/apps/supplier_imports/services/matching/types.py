from __future__ import annotations

from dataclasses import dataclass

from apps.catalog.models import Product


@dataclass(frozen=True)
class MatchDecision:
    status: str
    reason: str
    matched_product: Product | None
    candidate_products: tuple[Product, ...]
