from django.db.models import QuerySet

from apps.marketing.models import HeroSlide, HeroSliderSettings


def get_active_hero_slides_queryset() -> QuerySet[HeroSlide]:
    settings_obj = HeroSliderSettings.objects.filter(code="default").first()
    max_slides = settings_obj.max_active_slides if settings_obj else 10
    return HeroSlide.objects.filter(is_active=True).order_by("sort_order")[:max_slides]
