from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone

from apps.catalog.models import Product
from apps.pricing.models import PriceOverride, SupplierOffer

DEFAULT_PRICE_FRESHNESS_HOURS = 24


@dataclass(frozen=True)
class ProductActivitySyncResult:
    activated: int
    deactivated: int
    deactivated_no_fresh_offer: int
    deactivated_invalid_price: int
    deactivated_unsafe_markup: int
    supplier_offers_zeroed: int
    freshness_hours: int
    cutoff_at: timezone.datetime


def build_price_freshness_cutoff(*, freshness_hours: int = DEFAULT_PRICE_FRESHNESS_HOURS):
    normalized_hours = max(int(freshness_hours), 1)
    return timezone.now() - timedelta(hours=normalized_hours)


def ensure_product_active_on_price_update(*, product: Product) -> bool:
    if product.is_active:
        return False

    now = timezone.now()
    product.is_active = True
    if product.published_at is None:
        product.published_at = now
        product.save(update_fields=("is_active", "published_at", "updated_at"))
        return True

    product.save(update_fields=("is_active", "updated_at"))
    return True


def sync_products_activity_by_price_freshness(
    *,
    freshness_hours: int = DEFAULT_PRICE_FRESHNESS_HOURS,
    cutoff_at=None,
) -> ProductActivitySyncResult:
    normalized_hours = max(int(freshness_hours), 1)
    cutoff = cutoff_at or build_price_freshness_cutoff(freshness_hours=normalized_hours)
    now = timezone.now()

    eligible_products = _product_activity_queryset(cutoff=cutoff).filter(
        has_fresh_offer=True,
    ).filter(
        Q(has_active_override=True) | Q(has_safe_auto_price=True),
    )
    eligible_product_ids = eligible_products.values("id")

    activated = Product.objects.filter(
        is_active=False,
        id__in=eligible_product_ids,
    ).update(is_active=True, published_at=now)

    active_products = _product_activity_queryset(cutoff=cutoff).filter(is_active=True)
    deactivated_no_fresh_offer = active_products.filter(has_fresh_offer=False).count()
    active_with_fresh_offer = active_products.filter(has_fresh_offer=True)
    deactivated_invalid_price = active_with_fresh_offer.filter(
        has_active_override=False,
    ).filter(
        Q(product_price__isnull=True)
        | Q(product_price__final_price__lte=0)
        | Q(product_price__purchase_price__lte=0)
    ).count()
    deactivated_unsafe_markup = active_with_fresh_offer.filter(
        has_active_override=False,
        product_price__isnull=False,
        product_price__final_price__gt=0,
        product_price__purchase_price__gt=0,
        has_safe_auto_price=False,
    ).count()

    deactivated = Product.objects.filter(
        is_active=True,
    ).exclude(
        id__in=eligible_product_ids,
    ).update(is_active=False)

    supplier_offers_zeroed = SupplierOffer.objects.filter(
        product__is_active=False,
    ).filter(
        Q(last_seen_at__isnull=True) | Q(last_seen_at__lt=cutoff),
    ).filter(
        Q(stock_qty__gt=0) | Q(is_available=True),
    ).update(
        stock_qty=0,
        is_available=False,
    )

    return ProductActivitySyncResult(
        activated=int(activated),
        deactivated=int(deactivated),
        deactivated_no_fresh_offer=int(deactivated_no_fresh_offer),
        deactivated_invalid_price=int(deactivated_invalid_price),
        deactivated_unsafe_markup=int(deactivated_unsafe_markup),
        supplier_offers_zeroed=int(supplier_offers_zeroed),
        freshness_hours=normalized_hours,
        cutoff_at=cutoff,
    )


def _product_activity_queryset(*, cutoff):
    fresh_offer = SupplierOffer.objects.filter(
        product_id=OuterRef("id"),
        is_available=True,
        stock_qty__gt=0,
        purchase_price__gt=0,
    ).filter(
        Q(last_seen_at__gte=cutoff) | Q(last_seen_at__isnull=True, updated_at__gte=cutoff),
    )
    active_override = PriceOverride.objects.filter(
        product_id=OuterRef("id"),
        is_active=True,
        override_price__gt=0,
    )

    return (
        Product.objects.annotate(
            has_fresh_offer=Exists(fresh_offer),
            has_active_override=Exists(active_override),
        )
        .annotate(
            has_safe_auto_price=Q(
                product_price__isnull=False,
                product_price__purchase_price__gt=0,
                product_price__final_price__gt=F("product_price__purchase_price"),
            )
        )
    )
