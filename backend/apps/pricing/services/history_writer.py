from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.catalog.models import Product
from apps.pricing.models import PriceHistory, ProductPrice
from apps.pricing.services.rounding import quantize_money

User = get_user_model()


class PriceHistoryWriter:
    def write(
        self,
        *,
        product: Product,
        product_price: ProductPrice,
        old_price: Decimal | None,
        new_price: Decimal,
        source: str,
        comment: str = "",
        changed_by: User | None = None,
    ) -> PriceHistory | None:
        old_amount = quantize_money(old_price) if old_price is not None else None
        new_amount = quantize_money(new_price)

        if old_amount is not None and old_amount == new_amount:
            return None

        return PriceHistory.objects.create(
            product=product,
            product_price=product_price,
            old_price=old_amount,
            new_price=new_amount,
            source=source,
            comment=comment,
            changed_by=changed_by,
        )
