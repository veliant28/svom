from __future__ import annotations

from apps.core.services.demo_seed.media import ensure_placeholder_media_file
from apps.marketing.models import HeroSlide, HeroSliderSettings, PromoBanner, PromoBannerSettings


def seed_marketing_demo() -> dict[str, int]:
    hero_count = _seed_hero_slides()
    promo_count = _seed_promo_banners()

    HeroSliderSettings.objects.update_or_create(
        code="default",
        defaults={
            "autoplay_enabled": True,
            "transition_interval_ms": 5000,
            "transition_speed_ms": 700,
            "transition_effect": "crossfade",
            "max_active_slides": 10,
        },
    )

    PromoBannerSettings.objects.update_or_create(
        code="default",
        defaults={
            "autoplay_enabled": True,
            "transition_interval_ms": 4500,
            "transition_speed_ms": 650,
            "transition_effect": "fade",
            "max_active_banners": 5,
        },
    )

    return {
        "hero_slides": hero_count,
        "promo_banners": promo_count,
        "hero_slider_settings": 1,
        "promo_banner_settings": 1,
    }


def _seed_hero_slides() -> int:
    payload = [
        {
            "sort_order": 1,
            "title_uk": "Нічна видимість",
            "title_ru": "Ночная видимость",
            "title_en": "Night visibility",
            "subtitle_uk": "Рух без компромісів",
            "subtitle_ru": "Движение без компромиссов",
            "subtitle_en": "Drive without compromise",
        },
        {
            "sort_order": 2,
            "title_uk": "Точність на швидкості",
            "title_ru": "Точность на скорости",
            "title_en": "Precision at speed",
            "subtitle_uk": "Рух без компромісів",
            "subtitle_ru": "Движение без компромиссов",
            "subtitle_en": "Drive without compromise",
        },
        {
            "sort_order": 3,
            "title_uk": "Характер у кожній деталі",
            "title_ru": "Характер в каждой детали",
            "title_en": "Power in every detail",
            "subtitle_uk": "Рух без компромісів",
            "subtitle_ru": "Движение без компромиссов",
            "subtitle_en": "Drive without compromise",
        },
    ]

    created_or_updated = 0
    for item in payload:
        desktop_path = ensure_placeholder_media_file(
            f"marketing/hero/desktop/demo-hero-{item['sort_order']}.png"
        )
        mobile_path = ensure_placeholder_media_file(
            f"marketing/hero/mobile/demo-hero-{item['sort_order']}.png"
        )

        HeroSlide.objects.update_or_create(
            title_en=item["title_en"],
            defaults={
                "title_uk": item["title_uk"],
                "title_ru": item["title_ru"],
                "subtitle_uk": item["subtitle_uk"],
                "subtitle_ru": item["subtitle_ru"],
                "subtitle_en": item["subtitle_en"],
                "desktop_image": desktop_path,
                "mobile_image": mobile_path,
                "sort_order": item["sort_order"],
                "is_active": True,
                "cta_url": "/uk/catalog",
            },
        )
        created_or_updated += 1

    return created_or_updated


def _seed_promo_banners() -> int:
    payload = [
        {"sort_order": 1, "title": "Oil Service Week", "description": "Engine oils and filters with demo discounts."},
        {"sort_order": 2, "title": "Lighting Promo", "description": "Headlight bulbs for city and highway usage."},
        {"sort_order": 3, "title": "Garage Essentials", "description": "Starter pack for your first maintenance cycle."},
    ]

    created_or_updated = 0
    for item in payload:
        image_path = ensure_placeholder_media_file(
            f"marketing/promo/demo-promo-{item['sort_order']}.png"
        )
        PromoBanner.objects.update_or_create(
            title_en=item["title"],
            defaults={
                "title_uk": item["title"],
                "title_ru": item["title"],
                "description_uk": item["description"],
                "description_ru": item["description"],
                "description_en": item["description"],
                "image": image_path,
                "target_url": "/uk/catalog",
                "sort_order": item["sort_order"],
                "is_active": True,
            },
        )
        created_or_updated += 1

    return created_or_updated
