from __future__ import annotations

from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.models import Brand, Product
from apps.catalog.services import generate_unique_product_slug, sanitize_product_name
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
    brand_cache: dict[str, Brand],
    product_cache: dict[str, Product],
    supplier_offer_cache: dict[str, SupplierOffer],
) -> tuple[Product, bool, bool]:
    now = timezone.now()
    resolved_sku = selection.build_product_sku(supplier_sku=supplier_sku)
    existing_offer = supplier_offer_cache.get(supplier_sku)
    product = raw_offer.matched_product or (existing_offer.product if existing_offer is not None else None)

    if product is None:
        product = product_cache.get(resolved_sku)
        if product is None:
            brand = resolve_brand(raw_offer=raw_offer, brand_cache=brand_cache)
            name = resolve_product_name(raw_offer=raw_offer, supplier_sku=supplier_sku)
            preferred_slug = slugify(f"{name}-{raw_offer.supplier.code}-{supplier_sku}")[:300]
            product = Product.objects.create(
                sku=resolved_sku,
                article=(raw_offer.article or raw_offer.external_sku or supplier_sku)[:128],
                name=name,
                slug=generate_unique_product_slug(name=name, preferred_slug=preferred_slug),
                brand=brand,
                category=raw_offer.mapped_category,
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

    if raw_offer.mapped_category_id and product.category_id != raw_offer.mapped_category_id:
        product.category = raw_offer.mapped_category
        changed_fields.add("category")

    if not product.is_active:
        product.is_active = True
        changed_fields.add("is_active")
    if product.published_at is None:
        product.published_at = now
        changed_fields.add("published_at")

    if not raw_offer.matched_product_id:
        resolved_name = resolve_product_name(raw_offer=raw_offer, supplier_sku=supplier_sku)
        if resolved_name and product.name != resolved_name:
            product.name = resolved_name
            changed_fields.add("name")

        resolved_article = (raw_offer.article or raw_offer.external_sku or supplier_sku)[:128]
        if resolved_article and product.article != resolved_article:
            product.article = resolved_article
            changed_fields.add("article")

        brand = resolve_brand(raw_offer=raw_offer, brand_cache=brand_cache)
        if product.brand_id != brand.id:
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


def resolve_product_name(*, raw_offer: SupplierRawOffer, supplier_sku: str) -> str:
    cleaned = sanitize_product_name(raw_offer.product_name or "")
    if cleaned:
        return cleaned[:255]
    fallback = sanitize_product_name(raw_offer.article or raw_offer.external_sku or supplier_sku or "Supplier product")
    return fallback[:255] or "Supplier product"


def generate_unique_brand_slug(base_name: str) -> str:
    base = slugify(base_name).strip("-")[:130] or "brand"
    candidate = base
    index = 2
    while Brand.objects.filter(slug=candidate).exists():
        suffix = f"-{index}"
        candidate = f"{base[: max(1, 140 - len(suffix))]}{suffix}"
        index += 1
    return candidate
