from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.marketing.models import PromoBanner, PromoBannerSettings


def get_promo_banner_settings() -> PromoBannerSettings:
    settings_obj = PromoBannerSettings.objects.filter(code="default").first()
    if settings_obj is not None:
        return settings_obj
    return PromoBannerSettings.objects.create(code="default")


def get_active_promo_banners_queryset() -> QuerySet[PromoBanner]:
    settings_obj = get_promo_banner_settings()
    max_banners = max(1, min(int(settings_obj.max_active_banners or 5), 10))
    now = timezone.now()
    return (
        PromoBanner.objects.filter(is_active=True)
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        .order_by("sort_order", "created_at")[:max_banners]
    )
