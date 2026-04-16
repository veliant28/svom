from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.models import Brand, Product
from apps.catalog.services import generate_unique_product_slug, sanitize_product_name
from apps.pricing.models import PriceHistory, Supplier, SupplierOffer
from apps.pricing.services import ProductRepricer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand
from apps.supplier_imports.selectors import get_import_source_by_code, get_supplier_raw_offers_publish_queryset

_PUBLISHABLE_STATUSES = frozenset(
    {
        SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
        SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
    }
)


@dataclass(frozen=True)
class SupplierMappedPublishResult:
    supplier_code: str
    supplier_name: str
    raw_rows_scanned: int
    unique_latest_rows: int
    eligible_rows: int
    created_rows: int
    updated_rows: int
    skipped_rows: int
    error_rows: int
    products_created: int
    products_updated: int
    offers_created: int
    offers_updated: int
    raw_offer_links_updated: int
    repriced_products: int
    repricing_stats: dict[str, int]
    skip_reasons: dict[str, int]
    error_reasons: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "supplier_code": self.supplier_code,
            "supplier_name": self.supplier_name,
            "raw_rows_scanned": self.raw_rows_scanned,
            "unique_latest_rows": self.unique_latest_rows,
            "eligible_rows": self.eligible_rows,
            "created_rows": self.created_rows,
            "updated_rows": self.updated_rows,
            "skipped_rows": self.skipped_rows,
            "error_rows": self.error_rows,
            "products_created": self.products_created,
            "products_updated": self.products_updated,
            "offers_created": self.offers_created,
            "offers_updated": self.offers_updated,
            "raw_offer_links_updated": self.raw_offer_links_updated,
            "repriced_products": self.repriced_products,
            "repricing_stats": self.repricing_stats,
            "skip_reasons": self.skip_reasons,
            "error_reasons": self.error_reasons,
        }


@dataclass
class _PublishCounters:
    raw_rows_scanned: int = 0
    unique_latest_rows: int = 0
    eligible_rows: int = 0
    created_rows: int = 0
    updated_rows: int = 0
    skipped_rows: int = 0
    error_rows: int = 0
    products_created: int = 0
    products_updated: int = 0
    offers_created: int = 0
    offers_updated: int = 0
    raw_offer_links_updated: int = 0
    repriced_products: int = 0
    repricing_stats: dict[str, int] = field(default_factory=dict)
    skip_reasons: dict[str, int] = field(default_factory=dict)
    error_reasons: dict[str, int] = field(default_factory=dict)

    def add_skip(self, reason: str) -> None:
        self.skipped_rows += 1
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1

    def add_error(self, reason: str) -> None:
        self.error_rows += 1
        self.error_reasons[reason] = self.error_reasons.get(reason, 0) + 1


class SupplierMappedOffersPublishService:
    def publish_for_supplier(
        self,
        *,
        supplier_code: str,
        include_needs_review: bool = False,
        dry_run: bool = False,
        reprice_after_publish: bool = True,
    ) -> SupplierMappedPublishResult:
        source = get_import_source_by_code(supplier_code)
        supplier = source.supplier

        if dry_run:
            with transaction.atomic():
                result = self._publish(
                    supplier=supplier,
                    supplier_code=supplier_code,
                    include_needs_review=include_needs_review,
                    reprice_after_publish=reprice_after_publish,
                )
                transaction.set_rollback(True)
                return result

        return self._publish(
            supplier=supplier,
            supplier_code=supplier_code,
            include_needs_review=include_needs_review,
            reprice_after_publish=reprice_after_publish,
        )

    def _publish(
        self,
        *,
        supplier: Supplier,
        supplier_code: str,
        include_needs_review: bool,
        reprice_after_publish: bool,
    ) -> SupplierMappedPublishResult:
        counters = _PublishCounters()
        offer_key_seen: set[str] = set()
        affected_product_ids: set[str] = set()

        brand_cache = self._build_brand_cache()
        product_cache = self._build_product_cache()
        supplier_offer_cache = self._build_supplier_offer_cache(supplier=supplier)

        queryset = get_supplier_raw_offers_publish_queryset(supplier_code=supplier_code)
        for raw_offer in queryset.iterator(chunk_size=1000):
            counters.raw_rows_scanned += 1
            supplier_sku = self._resolve_supplier_sku(raw_offer=raw_offer)
            offer_key = supplier_sku.upper() if supplier_sku else f"row:{raw_offer.id}"
            if offer_key in offer_key_seen:
                counters.add_skip("older_history_row")
                continue

            offer_key_seen.add(offer_key)
            counters.unique_latest_rows += 1

            reason = self._resolve_skip_reason(
                raw_offer=raw_offer,
                supplier_sku=supplier_sku,
                include_needs_review=include_needs_review,
            )
            if reason:
                counters.add_skip(reason)
                continue

            counters.eligible_rows += 1
            try:
                with transaction.atomic():
                    product, product_created, product_updated = self._upsert_product(
                        raw_offer=raw_offer,
                        supplier_sku=supplier_sku,
                        brand_cache=brand_cache,
                        product_cache=product_cache,
                        supplier_offer_cache=supplier_offer_cache,
                    )
                    offer, offer_created, offer_updated = self._upsert_supplier_offer(
                        raw_offer=raw_offer,
                        product=product,
                        supplier_sku=supplier_sku,
                        supplier_offer_cache=supplier_offer_cache,
                    )

                    if raw_offer.matched_product_id != product.id:
                        raw_offer.matched_product = product
                        raw_offer.save(update_fields=("matched_product", "updated_at"))
                        counters.raw_offer_links_updated += 1

                if offer_created:
                    counters.created_rows += 1
                else:
                    counters.updated_rows += 1

                if product_created:
                    counters.products_created += 1
                if product_updated:
                    counters.products_updated += 1
                if offer_created:
                    counters.offers_created += 1
                if offer_updated:
                    counters.offers_updated += 1

                affected_product_ids.add(str(offer.product_id))
            except Exception as exc:
                counters.add_error(type(exc).__name__)

        if reprice_after_publish and affected_product_ids:
            stats = ProductRepricer().recalculate_products(
                Product.objects.filter(id__in=affected_product_ids),
                source=PriceHistory.SOURCE_IMPORT,
                trigger_note=f"publish_mapped:{supplier_code}",
            )
            counters.repricing_stats = stats
            counters.repriced_products = int(stats.get("repriced", 0))

        return SupplierMappedPublishResult(
            supplier_code=supplier_code,
            supplier_name=supplier.name,
            raw_rows_scanned=counters.raw_rows_scanned,
            unique_latest_rows=counters.unique_latest_rows,
            eligible_rows=counters.eligible_rows,
            created_rows=counters.created_rows,
            updated_rows=counters.updated_rows,
            skipped_rows=counters.skipped_rows,
            error_rows=counters.error_rows,
            products_created=counters.products_created,
            products_updated=counters.products_updated,
            offers_created=counters.offers_created,
            offers_updated=counters.offers_updated,
            raw_offer_links_updated=counters.raw_offer_links_updated,
            repriced_products=counters.repriced_products,
            repricing_stats=counters.repricing_stats,
            skip_reasons=counters.skip_reasons,
            error_reasons=counters.error_reasons,
        )

    def _resolve_skip_reason(
        self,
        *,
        raw_offer: SupplierRawOffer,
        supplier_sku: str,
        include_needs_review: bool,
    ) -> str:
        if raw_offer.mapped_category_id is None:
            return "missing_mapped_category"

        if raw_offer.category_mapping_status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW and not include_needs_review:
            return "needs_review"

        if raw_offer.category_mapping_status not in _PUBLISHABLE_STATUSES:
            if include_needs_review and raw_offer.category_mapping_status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW:
                pass
            else:
                return f"status_{raw_offer.category_mapping_status or 'unknown'}"

        if raw_offer.price is None:
            return "missing_price"
        if raw_offer.price <= Decimal("0"):
            return "non_positive_price"

        if not sanitize_product_name(raw_offer.product_name):
            return "missing_product_name"
        if not supplier_sku:
            return "missing_supplier_sku"
        return ""

    def _build_brand_cache(self) -> dict[str, Brand]:
        mapping: dict[str, Brand] = {}
        for brand in Brand.objects.all().order_by("name").iterator(chunk_size=500):
            normalized = normalize_brand(brand.name)
            if normalized and normalized not in mapping:
                mapping[normalized] = brand
        return mapping

    def _build_product_cache(self) -> dict[str, Product]:
        mapping: dict[str, Product] = {}
        queryset = Product.objects.select_related("brand", "category").order_by("sku")
        for product in queryset.iterator(chunk_size=500):
            mapping[product.sku] = product
        return mapping

    def _build_supplier_offer_cache(self, *, supplier: Supplier) -> dict[str, SupplierOffer]:
        mapping: dict[str, SupplierOffer] = {}
        queryset = SupplierOffer.objects.filter(supplier=supplier).select_related("product").order_by("-updated_at", "-created_at")
        for offer in queryset.iterator(chunk_size=1000):
            if offer.supplier_sku not in mapping:
                mapping[offer.supplier_sku] = offer
        return mapping

    def _upsert_product(
        self,
        *,
        raw_offer: SupplierRawOffer,
        supplier_sku: str,
        brand_cache: dict[str, Brand],
        product_cache: dict[str, Product],
        supplier_offer_cache: dict[str, SupplierOffer],
    ) -> tuple[Product, bool, bool]:
        now = timezone.now()
        resolved_sku = self._build_product_sku(supplier_sku=supplier_sku)
        existing_offer = supplier_offer_cache.get(supplier_sku)
        product = raw_offer.matched_product or (existing_offer.product if existing_offer is not None else None)

        if product is None:
            product = product_cache.get(resolved_sku)
            if product is None:
                brand = self._resolve_brand(raw_offer=raw_offer, brand_cache=brand_cache)
                name = self._resolve_product_name(raw_offer=raw_offer, supplier_sku=supplier_sku)
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
            resolved_name = self._resolve_product_name(raw_offer=raw_offer, supplier_sku=supplier_sku)
            if resolved_name and product.name != resolved_name:
                product.name = resolved_name
                changed_fields.add("name")

            resolved_article = (raw_offer.article or raw_offer.external_sku or supplier_sku)[:128]
            if resolved_article and product.article != resolved_article:
                product.article = resolved_article
                changed_fields.add("article")

            brand = self._resolve_brand(raw_offer=raw_offer, brand_cache=brand_cache)
            if product.brand_id != brand.id:
                product.brand = brand
                changed_fields.add("brand")

        if changed_fields:
            product.save(update_fields=tuple(sorted(changed_fields | {"updated_at"})))
            return product, False, True
        return product, False, False

    def _upsert_supplier_offer(
        self,
        *,
        raw_offer: SupplierRawOffer,
        product: Product,
        supplier_sku: str,
        supplier_offer_cache: dict[str, SupplierOffer],
    ) -> tuple[SupplierOffer, bool, bool]:
        offer = supplier_offer_cache.get(supplier_sku)
        is_available = raw_offer.stock_qty > 0 and bool(raw_offer.price and raw_offer.price > Decimal("0"))

        if offer is None:
            offer = SupplierOffer.objects.create(
                supplier=raw_offer.supplier,
                product=product,
                supplier_sku=supplier_sku,
                currency=raw_offer.currency,
                purchase_price=raw_offer.price,
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

    def _resolve_brand(self, *, raw_offer: SupplierRawOffer, brand_cache: dict[str, Brand]) -> Brand:
        source_name = sanitize_product_name(raw_offer.brand_name) or raw_offer.supplier.name or "UNKNOWN"
        normalized = normalize_brand(raw_offer.normalized_brand or source_name)
        if normalized in brand_cache:
            return brand_cache[normalized]

        slug = self._generate_unique_brand_slug(source_name)
        brand = Brand.objects.create(
            name=source_name[:120],
            slug=slug,
            is_active=True,
            published_at=timezone.now(),
        )
        brand_cache[normalized] = brand
        return brand

    def _resolve_product_name(self, *, raw_offer: SupplierRawOffer, supplier_sku: str) -> str:
        cleaned = sanitize_product_name(raw_offer.product_name or "")
        if cleaned:
            return cleaned[:255]
        fallback = sanitize_product_name(raw_offer.article or raw_offer.external_sku or supplier_sku or "Supplier product")
        return fallback[:255] or "Supplier product"

    def _resolve_supplier_sku(self, *, raw_offer: SupplierRawOffer) -> str:
        return (raw_offer.external_sku or raw_offer.article or "").strip()[:128]

    def _build_product_sku(self, *, supplier_sku: str) -> str:
        return supplier_sku[:64]

    def _generate_unique_brand_slug(self, base_name: str) -> str:
        base = slugify(base_name).strip("-")[:130] or "brand"
        candidate = base
        index = 2
        while Brand.objects.filter(slug=candidate).exists():
            suffix = f"-{index}"
            candidate = f"{base[: max(1, 140 - len(suffix))]}{suffix}"
            index += 1
        return candidate
