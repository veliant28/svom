from __future__ import annotations

from django.db.models import Count

from apps.catalog.models import Brand, Category, Product
from apps.seo.models import SeoMetaOverride, SeoMetaTemplate
from apps.seo.selectors.settings_selectors import (
    get_google_integration_settings,
    get_seo_site_settings,
    list_google_event_settings,
)


def get_seo_dashboard_payload() -> dict:
    seo_settings = get_seo_site_settings()
    google_settings = get_google_integration_settings()
    google_events = list_google_event_settings()

    product_count = Product.objects.count()
    category_count = Category.objects.count()
    brand_count = Brand.objects.count()
    active_overrides = SeoMetaOverride.objects.filter(is_active=True).count()
    active_templates = SeoMetaTemplate.objects.filter(is_active=True).count()

    # Current catalog entities do not expose native meta fields, so missing-meta
    # chart values remain empty until those fields are introduced.
    missing_meta_available = False
    missing_meta_by_type: list[dict] = []

    seo_health_by_entity = [
        {
            "entity": "product",
            "label": "Products",
            "total": product_count,
            "missing_title": 0,
            "missing_description": 0,
            "ok": 0,
        },
        {
            "entity": "category",
            "label": "Categories",
            "total": category_count,
            "missing_title": 0,
            "missing_description": 0,
            "ok": 0,
        },
        {
            "entity": "brand",
            "label": "Brands",
            "total": brand_count,
            "missing_title": 0,
            "missing_description": 0,
            "ok": 0,
        },
        {
            "entity": "override",
            "label": "Overrides",
            "total": active_overrides,
            "missing_title": 0,
            "missing_description": 0,
            "ok": active_overrides,
        },
        {
            "entity": "template",
            "label": "Templates",
            "total": active_templates,
            "missing_title": 0,
            "missing_description": 0,
            "ok": active_templates,
        },
    ]

    google_events_state = [
        {
            "event_name": event.event_name,
            "label": event.label,
            "enabled": bool(event.is_enabled),
        }
        for event in google_events
    ]

    templates_by_entity = list(
        SeoMetaTemplate.objects.filter(is_active=True)
        .values("entity_type")
        .annotate(total=Count("id"))
        .order_by("entity_type")
    )

    return {
        "products_count": product_count,
        "categories_count": category_count,
        "brands_count": brand_count,
        "active_overrides_count": active_overrides,
        "active_templates_count": active_templates,
        "sitemap_enabled": bool(seo_settings.sitemap_enabled),
        "google_enabled": bool(google_settings.is_enabled),
        "ga4_configured": bool(google_settings.ga4_measurement_id.strip()),
        "gtm_configured": bool(google_settings.gtm_container_id.strip()),
        "search_console_configured": bool(
            google_settings.search_console_verification_token.strip()
            or google_settings.google_site_verification_meta.strip()
        ),
        "missing_meta_available": missing_meta_available,
        "seo_health_by_entity": seo_health_by_entity,
        "missing_meta_by_type": missing_meta_by_type,
        "google_events_state": google_events_state,
        "templates_by_entity": templates_by_entity,
    }
