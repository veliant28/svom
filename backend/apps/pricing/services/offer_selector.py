from apps.catalog.models import Product
from apps.pricing.models import SupplierOffer
from apps.pricing.services.selector import OfferStrategy, SupplierOfferSelector


class OfferSelector:
    def __init__(self) -> None:
        self.selector = SupplierOfferSelector()

    def select_best_offer(self, product: Product) -> SupplierOffer | None:
        result = self.selector.select_for_product(
            product=product,
            quantity=1,
            strategy=OfferStrategy.BEST_OFFER,
        )
        return result.selected_offer
