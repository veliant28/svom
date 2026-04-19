from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from django.core.files.base import ContentFile

from apps.catalog.models import Product, ProductImage
from apps.pricing.models import SupplierOffer

from . import images, selection

ProgressCallback = Callable[[dict[str, int | str]], None]


@dataclass(frozen=True)
class GplImageBackfillResult:
    dry_run: bool
    rows_scanned: int
    unique_latest_rows: int
    eligible_rows: int
    initial_missing_products: int
    products_considered: int
    candidates_collected: int
    created_images: int
    failed_downloads: int
    skipped_existing: int
    skipped_no_product: int
    missing_image_url: int
    remaining_missing_products: int
    skip_reasons: dict[str, int]
    error_types: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "rows_scanned": self.rows_scanned,
            "unique_latest_rows": self.unique_latest_rows,
            "eligible_rows": self.eligible_rows,
            "initial_missing_products": self.initial_missing_products,
            "products_considered": self.products_considered,
            "candidates_collected": self.candidates_collected,
            "created_images": self.created_images,
            "failed_downloads": self.failed_downloads,
            "skipped_existing": self.skipped_existing,
            "skipped_no_product": self.skipped_no_product,
            "missing_image_url": self.missing_image_url,
            "remaining_missing_products": self.remaining_missing_products,
            "skip_reasons": self.skip_reasons,
            "error_types": self.error_types,
        }


@dataclass
class _BackfillCounters:
    rows_scanned: int = 0
    unique_latest_rows: int = 0
    eligible_rows: int = 0
    products_considered: int = 0
    candidates_collected: int = 0
    created_images: int = 0
    failed_downloads: int = 0
    skipped_existing: int = 0
    skipped_no_product: int = 0
    missing_image_url: int = 0
    skip_reasons: Counter[str] = field(default_factory=Counter)
    error_types: Counter[str] = field(default_factory=Counter)


@dataclass(frozen=True)
class _Candidate:
    product_id: str
    raw_offer_id: str
    image_url: str
    alt_text: str


def backfill_gpl_product_images(
    *,
    dry_run: bool = False,
    limit: int | None = None,
    batch_size: int = 400,
    max_workers: int = 10,
    include_needs_review: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> GplImageBackfillResult:
    normalized_batch_size = max(int(batch_size), 1)
    normalized_workers = max(int(max_workers), 1)
    normalized_limit = max(int(limit), 1) if limit is not None else None

    missing_product_ids_raw = list(
        Product.objects.filter(supplier_offers__supplier__code="gpl", images__isnull=True).values_list("id", flat=True).distinct()
    )
    missing_product_ids = {str(product_id) for product_id in missing_product_ids_raw}
    initial_missing = len(missing_product_ids)
    product_by_id = {str(product.id): product for product in Product.objects.filter(id__in=missing_product_ids_raw).only("id", "name")}
    supplier_sku_to_product_id = {
        sku: str(product_id)
        for sku, product_id in SupplierOffer.objects.filter(supplier__code="gpl").values_list("supplier_sku", "product_id")
    }

    counters = _BackfillCounters()
    candidates: list[_Candidate] = []
    seen_offer_keys: set[str] = set()
    seen_product_ids: set[str] = set()

    queryset = selection.get_publish_queryset(supplier_code="gpl")
    for raw_offer in queryset.iterator(chunk_size=1000):
        counters.rows_scanned += 1
        supplier_sku = selection.resolve_supplier_sku(raw_offer=raw_offer)
        offer_key = selection.build_offer_key(supplier_sku=supplier_sku, raw_offer_id=str(raw_offer.id))
        if offer_key in seen_offer_keys:
            continue
        seen_offer_keys.add(offer_key)
        counters.unique_latest_rows += 1

        reason = selection.resolve_skip_reason(
            raw_offer=raw_offer,
            supplier_sku=supplier_sku,
            include_needs_review=include_needs_review,
        )
        if reason:
            counters.skip_reasons[reason] += 1
            continue
        counters.eligible_rows += 1

        product = raw_offer.matched_product
        if product is None:
            product_id = supplier_sku_to_product_id.get(supplier_sku)
            product = product_by_id.get(product_id or "")
        if product is None:
            counters.skipped_no_product += 1
            continue

        product_id = str(product.id)
        if product_id not in missing_product_ids:
            continue
        if product_id in seen_product_ids:
            continue
        seen_product_ids.add(product_id)
        counters.products_considered += 1

        image_url = images.extract_image_url(raw_offer=raw_offer)
        if not image_url:
            counters.missing_image_url += 1
            continue

        candidates.append(
            _Candidate(
                product_id=product_id,
                raw_offer_id=str(raw_offer.id),
                image_url=image_url,
                alt_text=(product.name or "")[:255],
            )
        )
        counters.candidates_collected += 1
        if normalized_limit is not None and counters.candidates_collected >= normalized_limit:
            break

    for offset in range(0, len(candidates), normalized_batch_size):
        chunk = candidates[offset : offset + normalized_batch_size]
        futures = {}
        with ThreadPoolExecutor(max_workers=normalized_workers) as pool:
            for candidate in chunk:
                futures[pool.submit(images._download_image, candidate.image_url)] = candidate

            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    content, content_type = future.result()
                except Exception as exc:  # noqa: BLE001
                    counters.failed_downloads += 1
                    counters.error_types[type(exc).__name__] += 1
                    continue

                if dry_run:
                    counters.created_images += 1
                    continue

                if ProductImage.objects.filter(product_id=candidate.product_id).exists():
                    counters.skipped_existing += 1
                    continue

                product = product_by_id.get(candidate.product_id)
                if product is None:
                    product = Product.objects.filter(id=candidate.product_id).only("id", "name").first()
                    if product is None:
                        counters.skipped_no_product += 1
                        continue
                    product_by_id[candidate.product_id] = product

                extension = images._resolve_extension(image_url=candidate.image_url, content_type=content_type)
                filename = images._build_filename(product=product, image_url=candidate.image_url, extension=extension)
                image = ProductImage(
                    product=product,
                    alt_text=candidate.alt_text or product.name[:255],
                    is_primary=True,
                    sort_order=0,
                )
                image.image.save(filename, ContentFile(content), save=False)
                image.save()
                counters.created_images += 1

        if progress_callback is not None:
            progress_callback(
                {
                    "processed_candidates": min(offset + normalized_batch_size, len(candidates)),
                    "total_candidates": len(candidates),
                    "created_images": counters.created_images,
                    "failed_downloads": counters.failed_downloads,
                    "skipped_existing": counters.skipped_existing,
                }
            )

    remaining_missing = Product.objects.filter(supplier_offers__supplier__code="gpl", images__isnull=True).distinct().count()

    return GplImageBackfillResult(
        dry_run=dry_run,
        rows_scanned=counters.rows_scanned,
        unique_latest_rows=counters.unique_latest_rows,
        eligible_rows=counters.eligible_rows,
        initial_missing_products=initial_missing,
        products_considered=counters.products_considered,
        candidates_collected=counters.candidates_collected,
        created_images=counters.created_images,
        failed_downloads=counters.failed_downloads,
        skipped_existing=counters.skipped_existing,
        skipped_no_product=counters.skipped_no_product,
        missing_image_url=counters.missing_image_url,
        remaining_missing_products=remaining_missing,
        skip_reasons=dict(counters.skip_reasons),
        error_types=dict(counters.error_types),
    )
