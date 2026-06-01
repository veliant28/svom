from __future__ import annotations

import re

from django.utils.text import slugify

from apps.catalog.models import Product


_LETTER_RE = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ]")
_CODE_LIKE_SINGLE_TOKEN_RE = re.compile(r"^[A-Z0-9][A-Z0-9._/\-]{1,}$")
_LEADING_NUMERIC_PREFIX_RE = re.compile(r"^\s*\d{3,}\s+")


def sanitize_product_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def resolve_locale(locale: str | None) -> str:
    lang = str(locale or "").strip().lower()
    if lang.startswith("ru"):
        return "ru"
    if lang.startswith("en"):
        return "en"
    return "uk"


def is_code_like_product_name(value: str) -> bool:
    text = sanitize_product_name(value)
    if not text:
        return True
    if not _LETTER_RE.search(text):
        return True

    tokens = text.split()
    if len(tokens) == 1:
        token = tokens[0].upper()
        if _CODE_LIKE_SINGLE_TOKEN_RE.fullmatch(token):
            return True
    return False


def _strip_trailing_exact_candidate(title: str, candidate: str) -> str:
    text = sanitize_product_name(title)
    suffix = sanitize_product_name(candidate)
    if not text or not suffix:
        return text
    if len(text) <= len(suffix):
        return text
    if not text.upper().endswith(suffix.upper()):
        return text

    cut = len(text) - len(suffix)
    prefix = text[:cut].rstrip()
    if not prefix:
        return text

    boundary_idx = cut - 1
    if boundary_idx >= 0 and text[boundary_idx].isalnum():
        return text

    prefix = prefix.rstrip(" -–—:/|,;#()[]{}")
    if not prefix:
        return text
    if not _LETTER_RE.search(prefix):
        return text
    return prefix


def cleanup_product_display_candidate(*, product: Product, value: str) -> str:
    cleaned = sanitize_product_name(value)
    if not cleaned:
        return ""
    cleaned = _LEADING_NUMERIC_PREFIX_RE.sub("", cleaned).strip()
    candidates = (
        str(getattr(product, "article", "") or ""),
        str(getattr(product, "autodb_article_number", "") or ""),
        str(getattr(product, "sku", "") or ""),
    )
    for candidate in candidates:
        cleaned = _strip_trailing_exact_candidate(cleaned, candidate)
        cleaned = sanitize_product_name(cleaned)
    return cleaned


def _safe_product_brand_name(product: Product) -> str:
    # Prefer denormalized/public fields to avoid touching optional legacy brand tables.
    for field_name in ("display_brand_name", "autodb_supplier_name", "normalized_brand"):
        value = sanitize_product_name(str(getattr(product, field_name, "") or ""))
        if value:
            return value
    try:
        return sanitize_product_name(str(getattr(getattr(product, "brand", None), "name", "") or ""))
    except Exception:  # noqa: BLE001
        return ""


def build_product_public_name_fallback(*, product: Product, locale: str | None = None) -> str:
    category = getattr(product, "category", None)
    category_name = ""
    if category is not None and hasattr(category, "get_localized_name"):
        category_name = sanitize_product_name(category.get_localized_name(locale))
    if not category_name:
        category_name = "Товар"

    brand_name = _safe_product_brand_name(product)
    article = sanitize_product_name(str(getattr(product, "article", "") or getattr(product, "autodb_article_number", "") or ""))
    suffix = sanitize_product_name(" ".join(item for item in [brand_name, article] if item))
    if suffix:
        return f"{category_name} {suffix}"
    return category_name


def get_product_display_name_with_meta(
    product: Product,
    locale: str | None = None,
    *,
    unknown_label: str = "Товар",
) -> tuple[str, str]:
    ordered_i18n_fields: tuple[tuple[str, str], ...]
    lang = resolve_locale(locale)
    if lang == "ru":
        ordered_i18n_fields = (("name_ru", str(getattr(product, "name_ru", "") or "")), ("name_uk", str(getattr(product, "name_uk", "") or "")), ("name_en", str(getattr(product, "name_en", "") or "")))
    elif lang == "en":
        ordered_i18n_fields = (("name_en", str(getattr(product, "name_en", "") or "")), ("name_uk", str(getattr(product, "name_uk", "") or "")), ("name_ru", str(getattr(product, "name_ru", "") or "")))
    else:
        ordered_i18n_fields = (("name_uk", str(getattr(product, "name_uk", "") or "")), ("name_ru", str(getattr(product, "name_ru", "") or "")), ("name_en", str(getattr(product, "name_en", "") or "")))

    for source, raw_value in ordered_i18n_fields:
        candidate = cleanup_product_display_candidate(product=product, value=raw_value)
        if candidate and not is_code_like_product_name(candidate):
            return candidate, source

    fallback_candidates = (
        ("name", str(getattr(product, "name", "") or "")),
        ("name_source_text", str(getattr(product, "name_source_text", "") or "")),
    )
    for source, raw_value in fallback_candidates:
        candidate = cleanup_product_display_candidate(product=product, value=raw_value)
        if candidate and not is_code_like_product_name(candidate):
            return candidate, source

    if unknown_label != "Товар":
        brand_name = _safe_product_brand_name(product)
        article = sanitize_product_name(str(getattr(product, "article", "") or getattr(product, "autodb_article_number", "") or ""))
        suffix = sanitize_product_name(" ".join(item for item in (brand_name, article) if item))
        return (f"{unknown_label} {suffix}".strip(), "fallback")

    fallback = build_product_public_name_fallback(product=product, locale=locale)
    return fallback, "fallback"


def get_product_display_name(product: Product, locale: str | None = None) -> str:
    display_name, _ = get_product_display_name_with_meta(product=product, locale=locale)
    return display_name


def get_admin_display_name(product: Product) -> str:
    base_name = get_product_display_name(product, "uk")
    brand_name = _safe_product_brand_name(product)
    article = sanitize_product_name(str(getattr(product, "article", "") or getattr(product, "autodb_article_number", "") or ""))
    suffix = sanitize_product_name(" ".join(item for item in [brand_name, article] if item))
    if base_name and suffix:
        return f"{base_name} - {suffix}"
    return base_name or suffix


def generate_unique_product_slug(
    *,
    name: str,
    preferred_slug: str = "",
    exclude_product_id: str | None = None,
) -> str:
    source = preferred_slug or name
    base = slugify(source).strip("-")
    if not base:
        base = "product"

    base = base[:300]
    if not base:
        base = "product"

    candidate = base
    index = 2

    while True:
        queryset = Product.objects.filter(slug=candidate)
        if exclude_product_id:
            queryset = queryset.exclude(id=exclude_product_id)
        if not queryset.exists():
            return candidate

        suffix = f"-{index}"
        candidate = f"{base[: max(1, 300 - len(suffix))]}{suffix}"
        index += 1
