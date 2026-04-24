from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.catalog.models import Product
from apps.pricing.models import PriceHistory, PriceOverride, ProductPrice
from apps.pricing.services.calculator import PricingCalculator
from apps.pricing.services.history_writer import PriceHistoryWriter
from apps.pricing.services.offer_selector import OfferSelector
from apps.pricing.services.policy_resolver import PolicyResolver
from apps.pricing.services.product_activity import ensure_product_active_on_price_update
from apps.pricing.services.rounding import quantize_money

User = get_user_model()


@dataclass(frozen=True)
class RepriceResult:
    product_id: str
    status: str
    reason: str = ""


class ProductRepricer:
    def __init__(self) -> None:
        self.offer_selector = OfferSelector()
        self.policy_resolver = PolicyResolver()
        self.calculator = PricingCalculator()
        self.history_writer = PriceHistoryWriter()

    def recalculate_product(
        self,
        *,
        product: Product,
        source: str = PriceHistory.SOURCE_AUTO,
        trigger_note: str = "",
        changed_by: User | None = None,
    ) -> RepriceResult:
        product_price, _ = ProductPrice.objects.get_or_create(product=product)
        old_price = product_price.final_price

        override = PriceOverride.objects.filter(product=product, is_active=True).first()
        if override is not None:
            self._apply_override(
                product=product,
                product_price=product_price,
                override=override,
                old_price=old_price,
                trigger_note=trigger_note,
                changed_by=changed_by,
            )
            return RepriceResult(product_id=str(product.id), status="repriced", reason="override")

        if product_price.auto_calculation_locked:
            return RepriceResult(product_id=str(product.id), status="skipped", reason="locked")

        offer = self.offer_selector.select_best_offer(product)
        if offer is None:
            return RepriceResult(product_id=str(product.id), status="skipped", reason="no_offer")

        policy = self.policy_resolver.resolve_policy(product=product, offer=offer)
        calculated = self.calculator.calculate(offer=offer, policy=policy)

        product_price.currency = calculated.currency
        product_price.purchase_price = calculated.purchase_price
        product_price.logistics_cost = calculated.logistics_cost
        product_price.extra_cost = calculated.extra_cost
        product_price.landed_cost = calculated.landed_cost
        product_price.raw_sale_price = calculated.raw_sale_price
        product_price.final_price = calculated.final_price
        product_price.policy = policy
        product_price.recalculated_at = timezone.now()
        product_price.save(
            update_fields=(
                "currency",
                "purchase_price",
                "logistics_cost",
                "extra_cost",
                "landed_cost",
                "raw_sale_price",
                "final_price",
                "policy",
                "recalculated_at",
                "updated_at",
            )
        )
        ensure_product_active_on_price_update(product=product)

        self.history_writer.write(
            product=product,
            product_price=product_price,
            old_price=old_price,
            new_price=calculated.final_price,
            source=source,
            comment=trigger_note,
            changed_by=changed_by,
        )
        return RepriceResult(product_id=str(product.id), status="repriced")

    def recalculate_products(
        self,
        products,
        *,
        source: str = PriceHistory.SOURCE_AUTO,
        trigger_note: str = "",
        changed_by: User | None = None,
    ) -> dict[str, int]:
        stats = {"repriced": 0, "skipped": 0, "errors": 0}

        for product in products.iterator(chunk_size=200):
            try:
                result = self.recalculate_product(
                    product=product,
                    source=source,
                    trigger_note=trigger_note,
                    changed_by=changed_by,
                )
            except Exception:
                stats["errors"] += 1
                continue

            stats[result.status] = stats.get(result.status, 0) + 1

        return stats

    def _apply_override(
        self,
        *,
        product: Product,
        product_price: ProductPrice,
        override: PriceOverride,
        old_price: Decimal,
        trigger_note: str,
        changed_by: User | None,
    ) -> None:
        comment = f"Override applied. {override.reason}".strip()
        if trigger_note:
            comment = f"{comment} [{trigger_note}]"

        product_price.currency = override.currency
        product_price.final_price = quantize_money(override.override_price)
        product_price.raw_sale_price = quantize_money(override.override_price)
        product_price.policy = None
        product_price.recalculated_at = timezone.now()
        product_price.save(
            update_fields=(
                "currency",
                "final_price",
                "raw_sale_price",
                "policy",
                "recalculated_at",
                "updated_at",
            )
        )
        ensure_product_active_on_price_update(product=product)

        self.history_writer.write(
            product=product,
            product_price=product_price,
            old_price=old_price,
            new_price=override.override_price,
            source=PriceHistory.SOURCE_MANUAL,
            comment=comment,
            changed_by=changed_by,
        )
