from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.seo.constants import SEO_ALLOWED_TEMPLATE_PLACEHOLDERS
from apps.seo.models import SeoMetaOverride, SeoMetaTemplate, SeoSiteSettings
from apps.seo.selectors import get_seo_site_settings


def normalize_locale(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("ru"):
        return "ru"
    if normalized.startswith("en"):
        return "en"
    return "uk"


def sanitize_context(context: dict[str, Any] | None) -> dict[str, str]:
    source = context or {}
    result: dict[str, str] = {}
    for placeholder in SEO_ALLOWED_TEMPLATE_PLACEHOLDERS:
        key = placeholder.strip("{}")
        value = source.get(key, "")
        result[key] = str(value or "").strip()
    return result


def render_template(value: str, context: dict[str, str]) -> str:
    rendered = str(value or "")
    if not rendered:
        return ""
    for key, raw_value in context.items():
        rendered = rendered.replace(f"{{{key}}}", raw_value)
    return " ".join(rendered.split()).strip()


def localized_setting(settings: SeoSiteSettings, base: str, locale: str) -> str:
    safe_locale = normalize_locale(locale)
    candidate = getattr(settings, f"{base}_{safe_locale}", "")
    if candidate:
        return str(candidate).strip()
    if safe_locale != "uk":
        fallback = getattr(settings, f"{base}_uk", "")
        if fallback:
            return str(fallback).strip()
    return ""


@dataclass(frozen=True)
class ResolvedSeoMeta:
    meta_title: str
    meta_description: str
    h1: str
    canonical_url: str
    robots_directive: str
    og_title: str
    og_description: str
    og_image_url: str
    source: str


def resolve_seo_meta(
    *,
    path: str,
    locale: str,
    entity_type: str = "page",
    context: dict[str, Any] | None = None,
) -> ResolvedSeoMeta:
    settings = get_seo_site_settings()
    safe_locale = normalize_locale(locale)
    safe_path = normalize_path(path)
    safe_context = sanitize_context(context)
    base_canonical = str(settings.canonical_base_url or "").rstrip("/")

    override = (
        SeoMetaOverride.objects
        .filter(path=safe_path, locale=safe_locale, is_active=True)
        .order_by("-updated_at")
        .first()
    )
    if override is not None:
        return ResolvedSeoMeta(
            meta_title=str(override.meta_title or "").strip() or localized_setting(settings, "default_meta_title", safe_locale),
            meta_description=str(override.meta_description or "").strip() or localized_setting(settings, "default_meta_description", safe_locale),
            h1=str(override.h1 or "").strip() or safe_context.get("name", ""),
            canonical_url=str(override.canonical_url or "").strip() or build_canonical(base_canonical, safe_path),
            robots_directive=str(override.robots_directive or "").strip() or str(settings.default_robots_directive or ""),
            og_title=str(override.og_title or "").strip() or localized_setting(settings, "default_og_title", safe_locale),
            og_description=str(override.og_description or "").strip() or localized_setting(settings, "default_og_description", safe_locale),
            og_image_url=str(override.og_image_url or "").strip(),
            source="override",
        )

    template = (
        SeoMetaTemplate.objects
        .filter(entity_type=entity_type, locale=safe_locale, is_active=True)
        .order_by("-updated_at")
        .first()
    )
    if template is not None:
        meta_title = render_template(template.title_template, safe_context) or localized_setting(settings, "default_meta_title", safe_locale)
        meta_description = render_template(template.description_template, safe_context) or localized_setting(
            settings,
            "default_meta_description",
            safe_locale,
        )
        h1 = render_template(template.h1_template, safe_context) or safe_context.get("name", "")
        og_title = render_template(template.og_title_template, safe_context) or localized_setting(settings, "default_og_title", safe_locale)
        og_description = render_template(template.og_description_template, safe_context) or localized_setting(
            settings,
            "default_og_description",
            safe_locale,
        )
        return ResolvedSeoMeta(
            meta_title=meta_title,
            meta_description=meta_description,
            h1=h1,
            canonical_url=build_canonical(base_canonical, safe_path),
            robots_directive=str(settings.default_robots_directive or ""),
            og_title=og_title,
            og_description=og_description,
            og_image_url="",
            source="template",
        )

    return ResolvedSeoMeta(
        meta_title=localized_setting(settings, "default_meta_title", safe_locale) or safe_context.get("name", ""),
        meta_description=localized_setting(settings, "default_meta_description", safe_locale),
        h1=safe_context.get("name", ""),
        canonical_url=build_canonical(base_canonical, safe_path),
        robots_directive=str(settings.default_robots_directive or ""),
        og_title=localized_setting(settings, "default_og_title", safe_locale),
        og_description=localized_setting(settings, "default_og_description", safe_locale),
        og_image_url="",
        source="default",
    )


def normalize_path(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "/"
    if raw.startswith("http://") or raw.startswith("https://"):
        raw = "/" + raw.split("/", 3)[-1] if "/" in raw[8:] else "/"
    if not raw.startswith("/"):
        raw = f"/{raw}"
    return raw


def build_canonical(base_url: str, path: str) -> str:
    if not base_url:
        return ""
    normalized_path = normalize_path(path)
    return f"{base_url}{normalized_path}"
