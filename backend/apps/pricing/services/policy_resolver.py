from apps.catalog.models import Product
from apps.pricing.models import PricingPolicy, SupplierOffer


class PolicyResolver:
    def resolve_policy(self, product: Product, offer: SupplierOffer | None) -> PricingPolicy | None:
        policy_steps = [
            self._brand_category_policy(product),
            self._brand_policy(product),
            self._category_policy(product),
            self._supplier_policy(offer),
            self._global_policy(),
        ]

        for queryset in policy_steps:
            policy = queryset.first()
            if policy is not None:
                return policy

        return None

    def _base_queryset(self):
        return PricingPolicy.objects.filter(is_active=True).order_by("priority", "id")

    def _brand_category_policy(self, product: Product):
        return self._base_queryset().filter(
            scope=PricingPolicy.SCOPE_BRAND_CATEGORY,
            brand=product.brand,
            category=product.category,
        )

    def _brand_policy(self, product: Product):
        return self._base_queryset().filter(
            scope=PricingPolicy.SCOPE_BRAND,
            brand=product.brand,
        )

    def _category_policy(self, product: Product):
        return self._base_queryset().filter(
            scope=PricingPolicy.SCOPE_CATEGORY,
            category=product.category,
        )

    def _supplier_policy(self, offer: SupplierOffer | None):
        queryset = self._base_queryset().filter(scope=PricingPolicy.SCOPE_SUPPLIER)
        if offer is None:
            return queryset.none()
        return queryset.filter(supplier=offer.supplier)

    def _global_policy(self):
        return self._base_queryset().filter(scope=PricingPolicy.SCOPE_GLOBAL)
