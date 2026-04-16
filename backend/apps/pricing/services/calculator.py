from dataclasses import dataclass
from decimal import Decimal

from apps.pricing.models import PricingPolicy, SupplierOffer
from apps.pricing.services.rounding import quantize_money, to_decimal


@dataclass(frozen=True)
class PriceCalculationResult:
    currency: str
    purchase_price: Decimal
    logistics_cost: Decimal
    extra_cost: Decimal
    landed_cost: Decimal
    raw_sale_price: Decimal
    final_price: Decimal


class PricingCalculator:
    def calculate(
        self,
        offer: SupplierOffer,
        policy: PricingPolicy | None,
    ) -> PriceCalculationResult:
        purchase_price = quantize_money(offer.purchase_price)
        logistics_cost = Decimal("0.00")
        extra_cost = Decimal("0.00")
        landed_cost = purchase_price

        markup = self._calculate_markup(purchase_price, policy)
        raw_sale_price = quantize_money(landed_cost + markup)
        final_price = raw_sale_price

        return PriceCalculationResult(
            currency=offer.currency,
            purchase_price=purchase_price,
            logistics_cost=logistics_cost,
            extra_cost=extra_cost,
            landed_cost=landed_cost,
            raw_sale_price=raw_sale_price,
            final_price=final_price,
        )

    def _calculate_markup(
        self,
        purchase_price: Decimal,
        policy: PricingPolicy | None,
    ) -> Decimal:
        if policy is None:
            return Decimal("0")

        percent_markup = to_decimal(policy.percent_markup)
        percent_amount = purchase_price * percent_markup / Decimal("100")
        return quantize_money(percent_amount)
