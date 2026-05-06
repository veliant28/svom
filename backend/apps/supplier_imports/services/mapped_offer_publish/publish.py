from __future__ import annotations

from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.models import Brand, Product
from apps.catalog.services.autodb_category_mapping import resolve_autodb_category_for_raw_offer
from apps.catalog.services import generate_unique_product_slug, resolve_autodb_article_name, sanitize_product_name
from apps.pricing.models import Supplier, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.gpl_parser import extract_gpl_price_levels
from apps.supplier_imports.parsers.utils import normalize_brand

from . import selection


def build_brand_cache() -> dict[str, Brand]:
    mapping: dict[str, Brand] = {}
    for brand in Brand.objects.all().order_by("name").iterator(chunk_size=500):
        normalized = normalize_brand(brand.name)
        if normalized and normalized not in mapping:
            mapping[normalized] = brand
    return mapping


def build_product_cache() -> dict[str, Product]:
    mapping: dict[str, Product] = {}
    queryset = Product.objects.select_related("brand", "category").order_by("sku")
    for product in queryset.iterator(chunk_size=500):
        mapping[product.sku] = product
    return mapping


def build_supplier_offer_cache(*, supplier: Supplier) -> dict[str, SupplierOffer]:
    mapping: dict[str, SupplierOffer] = {}
    queryset = SupplierOffer.objects.filter(supplier=supplier).select_related("product").order_by("-updated_at", "-created_at")
    for offer in queryset.iterator(chunk_size=1000):
        if offer.supplier_sku not in mapping:
            mapping[offer.supplier_sku] = offer
    return mapping


def upsert_product(
    *,
    raw_offer: SupplierRawOffer,
    supplier_sku: str,
    autodb_name_cache: dict[tuple[str, str], str],
    brand_cache: dict[str, Brand],
    product_cache: dict[str, Product],
    supplier_offer_cache: dict[str, SupplierOffer],
) -> tuple[Product, bool, bool]:
    now = timezone.now()
    resolved_sku = selection.build_product_sku(supplier_sku=supplier_sku)
    existing_offer = supplier_offer_cache.get(supplier_sku)
    product = raw_offer.matched_product or (existing_offer.product if existing_offer is not None else None)
    is_manual_category = raw_offer.category_mapping_status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED
    mapped_category = raw_offer.mapped_category
    if mapped_category is None:
        mapped_category = resolve_autodb_category_for_raw_offer(raw_offer=raw_offer)

    if product is None:
        product = product_cache.get(resolved_sku)
        if product is None:
            brand = resolve_brand(raw_offer=raw_offer, brand_cache=brand_cache)
            name = resolve_product_name(raw_offer=raw_offer, autodb_name_cache=autodb_name_cache)
            name_uk, name_ru, name_en = build_product_i18n_names(name=name)
            preferred_slug = slugify(f"{name}-{resolved_sku}")[:300]
            product = Product.objects.create(
                sku=resolved_sku,
                article=(raw_offer.article or raw_offer.external_sku or supplier_sku)[:128],
                name=name,
                name_uk=name_uk,
                name_ru=name_ru,
                name_en=name_en,
                slug=generate_unique_product_slug(name=name, preferred_slug=preferred_slug),
                brand=brand,
                category=mapped_category or raw_offer.mapped_category,
                category_manually_locked=is_manual_category,
                is_active=True,
                published_at=now,
            )
            product_cache[product.sku] = product
            return product, True, False

    changed_fields: set[str] = set()
    if product.sku != resolved_sku:
        conflicting_product = product_cache.get(resolved_sku)
        if conflicting_product is not None and conflicting_product.id != product.id:
            raise RuntimeError("sku_conflict")
        product_cache.pop(product.sku, None)
        product.sku = resolved_sku
        product_cache[resolved_sku] = product
        changed_fields.add("sku")

    if (
        mapped_category is not None
        and product.category_id != mapped_category.id
        and not product.category_manually_locked
    ):
        product.category = mapped_category
        changed_fields.add("category")

    if is_manual_category and not product.category_manually_locked:
        product.category_manually_locked = True
        changed_fields.add("category_manually_locked")

    if not product.is_active:
        product.is_active = True
        changed_fields.add("is_active")
    if product.published_at is None:
        product.published_at = now
        changed_fields.add("published_at")

    if not raw_offer.matched_product_id:
        resolved_name = resolve_product_name(raw_offer=raw_offer, autodb_name_cache=autodb_name_cache)
        name_uk, name_ru, name_en = build_product_i18n_names(name=resolved_name)
        if resolved_name and product.name != resolved_name:
            product.name = resolved_name
            changed_fields.add("name")
        if name_uk and product.name_uk != name_uk:
            product.name_uk = name_uk
            changed_fields.add("name_uk")
        if name_ru and product.name_ru != name_ru:
            product.name_ru = name_ru
            changed_fields.add("name_ru")
        if name_en and product.name_en != name_en:
            product.name_en = name_en
            changed_fields.add("name_en")

        resolved_article = (raw_offer.article or raw_offer.external_sku or supplier_sku)[:128]
        if resolved_article and not product.article:
            product.article = resolved_article
            changed_fields.add("article")

        brand = resolve_brand(raw_offer=raw_offer, brand_cache=brand_cache)
        if product.brand_id is None:
            product.brand = brand
            changed_fields.add("brand")

    if changed_fields:
        product.save(update_fields=tuple(sorted(changed_fields | {"updated_at"})))
        return product, False, True
    return product, False, False


def upsert_supplier_offer(
    *,
    raw_offer: SupplierRawOffer,
    product: Product,
    supplier_sku: str,
    supplier_offer_cache: dict[str, SupplierOffer],
) -> tuple[SupplierOffer, bool, bool]:
    offer = supplier_offer_cache.get(supplier_sku)
    is_available = raw_offer.stock_qty > 0 and bool(raw_offer.price and raw_offer.price > 0)
    price_levels = _extract_price_levels(raw_offer=raw_offer)

    if offer is None:
        offer = SupplierOffer.objects.create(
            supplier=raw_offer.supplier,
            product=product,
            supplier_sku=supplier_sku,
            currency=raw_offer.currency,
            purchase_price=raw_offer.price,
            price_levels=price_levels,
            stock_qty=max(raw_offer.stock_qty, 0),
            lead_time_days=max(raw_offer.lead_time_days, 0),
            is_available=is_available,
        )
        supplier_offer_cache[supplier_sku] = offer
        return offer, True, False

    changed_fields: set[str] = set()
    if offer.product_id != product.id:
        offer.product = product
        changed_fields.add("product")
    if offer.currency != raw_offer.currency:
        offer.currency = raw_offer.currency
        changed_fields.add("currency")
    if offer.purchase_price != raw_offer.price:
        offer.purchase_price = raw_offer.price
        changed_fields.add("purchase_price")
    if offer.price_levels != price_levels:
        offer.price_levels = price_levels
        changed_fields.add("price_levels")

    stock_qty = max(raw_offer.stock_qty, 0)
    if offer.stock_qty != stock_qty:
        offer.stock_qty = stock_qty
        changed_fields.add("stock_qty")

    lead_time_days = max(raw_offer.lead_time_days, 0)
    if offer.lead_time_days != lead_time_days:
        offer.lead_time_days = lead_time_days
        changed_fields.add("lead_time_days")
    if offer.is_available != is_available:
        offer.is_available = is_available
        changed_fields.add("is_available")

    if changed_fields:
        offer.save(update_fields=tuple(sorted(changed_fields | {"updated_at"})))
        return offer, False, True
    return offer, False, False


def _extract_price_levels(*, raw_offer: SupplierRawOffer) -> list[dict]:
    source_code = str(getattr(raw_offer.source, "code", "") or "").lower()
    if source_code != "gpl":
        return []
    return extract_gpl_price_levels(item=raw_offer.raw_payload or {}, default_currency=raw_offer.currency)


def resolve_brand(*, raw_offer: SupplierRawOffer, brand_cache: dict[str, Brand]) -> Brand:
    source_name = sanitize_product_name(raw_offer.brand_name) or raw_offer.supplier.name or "UNKNOWN"
    normalized = normalize_brand(raw_offer.normalized_brand or source_name)
    if normalized in brand_cache:
        return brand_cache[normalized]

    slug = generate_unique_brand_slug(source_name)
    brand = Brand.objects.create(
        name=source_name[:120],
        slug=slug,
        is_active=True,
        published_at=timezone.now(),
    )
    brand_cache[normalized] = brand
    return brand


def resolve_product_name(*, raw_offer: SupplierRawOffer, autodb_name_cache: dict[tuple[str, str], str]) -> str:
    article_value = str(raw_offer.article or raw_offer.external_sku or raw_offer.normalized_article or "").strip()
    normalized_brand = str(raw_offer.normalized_brand or raw_offer.brand_name or "").strip()
    cache_key = (article_value, normalized_brand)
    if cache_key not in autodb_name_cache:
        autodb_name_cache[cache_key] = resolve_autodb_article_name(
            normalized_article=article_value,
            normalized_brand=normalized_brand,
            prefer_live=True,
        )
    resolved = sanitize_product_name(autodb_name_cache.get(cache_key) or "")[:255]
    if resolved:
        return resolved
    fallback = sanitize_product_name(raw_offer.article or raw_offer.external_sku or "Product")[:255]
    return fallback or "Product"


def build_product_i18n_names(*, name: str) -> tuple[str, str, str]:
    clean = sanitize_product_name(name)[:255]
    if not clean:
        return "", "", ""
    # Auto parts names are mostly language-agnostic references.
    return clean, clean, clean


def generate_unique_brand_slug(base_name: str) -> str:
    base = slugify(base_name).strip("-")[:130] or "brand"
    candidate = base
    index = 2
    while Brand.objects.filter(slug=candidate).exists():
        suffix = f"-{index}"
        candidate = f"{base[: max(1, 140 - len(suffix))]}{suffix}"
        index += 1
    return candidate
