from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.catalog.models import Product

DEFAULT_PRICE_FRESHNESS_HOURS = 24


@dataclass(frozen=True)
class ProductActivitySyncResult:
    activated: int
    deactivated: int
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

    activated = Product.objects.filter(
        is_active=False,
        product_price__updated_at__gte=cutoff,
    ).update(is_active=True, published_at=now)

    deactivated = Product.objects.filter(
        is_active=True,
    ).filter(
        Q(product_price__isnull=True) | Q(product_price__updated_at__lt=cutoff),
    ).update(is_active=False)

    return ProductActivitySyncResult(
        activated=int(activated),
        deactivated=int(deactivated),
        freshness_hours=normalized_hours,
        cutoff_at=cutoff,
    )
