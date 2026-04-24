from __future__ import annotations

from django.utils import timezone

from apps.catalog.models import Brand, Category, Product
from apps.seo.models import SeoSiteSettings
from apps.seo.selectors import get_seo_site_settings


def render_robots_preview(settings: SeoSiteSettings) -> str:
    raw_robots = str(settings.robots_txt or "").strip()
    if raw_robots:
        return raw_robots

    lines = [
        "User-agent: *",
        "Allow: /",
    ]
    directive = str(settings.default_robots_directive or "").strip().lower()
    if directive and "noindex" in directive:
        lines = [
            "User-agent: *",
            "Disallow: /",
        ]
    base_url = str(settings.canonical_base_url or "").strip().rstrip("/")
    if settings.sitemap_enabled and base_url:
        lines.append(f"Sitemap: {base_url}/sitemap.xml")
    return "\n".join(lines)


def rebuild_sitemap() -> dict[str, object]:
    settings = get_seo_site_settings()
    settings.sitemap_last_rebuild_at = timezone.now()
    settings.save(update_fields=("sitemap_last_rebuild_at", "updated_at"))

    base_url = str(settings.canonical_base_url or "").strip().rstrip("/")
    sitemap_url = f"{base_url}/sitemap.xml" if base_url else ""

    return {
        "rebuild_started": True,
        "sitemap_url": sitemap_url,
        "sitemap_enabled": bool(settings.sitemap_enabled),
        "product_sitemap_enabled": bool(settings.product_sitemap_enabled),
        "category_sitemap_enabled": bool(settings.category_sitemap_enabled),
        "brand_sitemap_enabled": bool(settings.brand_sitemap_enabled),
        "products_count": Product.objects.count(),
        "categories_count": Category.objects.count(),
        "brands_count": Brand.objects.count(),
        "rebuilt_at": settings.sitemap_last_rebuild_at,
    }
