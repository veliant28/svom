from django.db.models import QuerySet

from apps.marketing.models import HeroSlide, HeroSliderSettings


def get_hero_slider_settings() -> HeroSliderSettings:
    settings_obj = HeroSliderSettings.objects.filter(code="default").first()
    if settings_obj is not None:
        return settings_obj
    return HeroSliderSettings.objects.create(code="default")


def get_active_hero_slides_queryset() -> QuerySet[HeroSlide]:
    settings_obj = get_hero_slider_settings()
    max_slides = max(1, min(int(settings_obj.max_active_slides or 10), 10))
    return HeroSlide.objects.filter(is_active=True).order_by("sort_order", "created_at")[:max_slides]
