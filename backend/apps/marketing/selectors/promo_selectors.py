from django.db.models import QuerySet

from apps.marketing.models import PromoBanner, PromoBannerSettings


def get_active_promo_banners_queryset() -> QuerySet[PromoBanner]:
    settings_obj = PromoBannerSettings.objects.filter(code="default").first()
    max_banners = settings_obj.max_active_banners if settings_obj else 5
    return PromoBanner.objects.filter(is_active=True).order_by("sort_order")[:max_banners]
