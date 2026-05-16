from __future__ import annotations

import time

from apps.catalog.models import Product
from apps.pricing.models import SupplierOffer
from apps.supplier_imports.services.gpl_images import GplProductImageService

from .persistence_helpers import (
    _bulk_attach_utr_detail_ids,
    _bulk_sync_gpl_product_articles,
    _elapsed_seconds,
    _should_disable_missing_offers,
)


def apply_current_offers_changes(
    *,
    dry_run: bool,
    source,
    seen_supplier_skus: set[str],
    valid_rows: dict[tuple[str, str], dict],
    now,
    timings: dict,
    bootstrap_products_would_create: int,
    created: int,
    updated: int,
    affected_products: set[str],
    utr_detail_updates: dict[str, str],
    gpl_product_article_updates: dict[str, str],
    is_gpl_source: bool,
) -> tuple[int, int, int, dict[str, int], set[str], dict]:
    bootstrap_products_would_reuse = 0

    if dry_run:
        dry_run_started = time.perf_counter()
        existing_keys = set(
            SupplierOffer.objects.filter(
                supplier=source.supplier,
                supplier_sku__in=seen_supplier_skus,
            ).values_list("product_id", "supplier_sku")
        )
        existing_str_keys = {(str(product_id), sku) for product_id, sku in existing_keys}
        created = sum(1 for key in valid_rows if key not in existing_str_keys)
        updated = max(len(valid_rows) - created, 0)
        bootstrap_products_would_reuse = max(len(valid_rows) - bootstrap_products_would_create, 0)
        timings["dry_run_existing_lookup_sec"] = _elapsed_seconds(dry_run_started)
    elif valid_rows:
        existing_load_started = time.perf_counter()
        existing_offers = list(
            SupplierOffer.objects.filter(
                supplier=source.supplier,
                supplier_sku__in=seen_supplier_skus,
            ).values(
                "id",
                "product_id",
                "supplier_sku",
                "currency",
                "purchase_price",
                "price_levels",
                "stock_qty",
                "lead_time_days",
                "is_available",
            )
        )
        timings["existing_offers_load_sec"] = _elapsed_seconds(existing_load_started)
        timings["existing_offers_loaded"] = len(existing_offers)

        existing_index_started = time.perf_counter()
        existing_by_key = {(str(offer["product_id"]), offer["supplier_sku"]): offer for offer in existing_offers}
        existing_by_sku: dict[str, list[dict]] = {}
        for existing in existing_offers:
            existing_by_sku.setdefault(existing["supplier_sku"], []).append(existing)
        timings["existing_index_build_sec"] = _elapsed_seconds(existing_index_started)

        offers_to_create: list[SupplierOffer] = []
        offers_to_update: list[SupplierOffer] = []
        stale_offers_to_disable: list[SupplierOffer] = []
        seen_existing_offer_ids: list[str] = []

        diff_started = time.perf_counter()
        for key, row in valid_rows.items():
            product_id, supplier_sku = key
            existing = existing_by_key.get(key)
            if existing is None:
                offers_to_create.append(
                    SupplierOffer(
                        supplier=source.supplier,
                        product=row["product"],
                        supplier_sku=supplier_sku,
                        currency=row["currency"],
                        purchase_price=row["purchase_price"],
                        price_levels=row["price_levels"],
                        stock_qty=row["stock_qty"],
                        lead_time_days=row["lead_time_days"],
                        is_available=row["is_available"],
                        last_seen_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )
                affected_products.add(product_id)
            else:
                seen_existing_offer_ids.append(str(existing["id"]))
                changed = (
                    existing["currency"] != row["currency"]
                    or existing["purchase_price"] != row["purchase_price"]
                    or existing["price_levels"] != row["price_levels"]
                    or existing["stock_qty"] != row["stock_qty"]
                    or existing["lead_time_days"] != row["lead_time_days"]
                    or existing["is_available"] != row["is_available"]
                )
                if changed:
                    offers_to_update.append(
                        SupplierOffer(
                            id=existing["id"],
                            currency=row["currency"],
                            purchase_price=row["purchase_price"],
                            price_levels=row["price_levels"],
                            stock_qty=row["stock_qty"],
                            lead_time_days=row["lead_time_days"],
                            is_available=row["is_available"],
                            last_seen_at=now,
                            updated_at=now,
                        )
                    )
                    affected_products.add(product_id)

            for stale in existing_by_sku.get(supplier_sku, []):
                if str(stale["product_id"]) == product_id:
                    continue
                if stale["is_available"] or stale["stock_qty"] != 0:
                    stale_offers_to_disable.append(
                        SupplierOffer(
                            id=stale["id"],
                            stock_qty=0,
                            is_available=False,
                            updated_at=now,
                        )
                    )
                    affected_products.add(str(stale["product_id"]))
        timings["diff_rows_sec"] = _elapsed_seconds(diff_started)
        timings["offers_to_create"] = len(offers_to_create)
        timings["offers_to_update"] = len(offers_to_update)
        timings["stale_offers_to_disable"] = len(stale_offers_to_disable)
        timings["seen_existing_offers"] = len(seen_existing_offer_ids)

        if offers_to_create:
            bulk_create_started = time.perf_counter()
            SupplierOffer.objects.bulk_create(offers_to_create, batch_size=1000)
            created += len(offers_to_create)
            timings["offers_bulk_create_sec"] = _elapsed_seconds(bulk_create_started)
        else:
            timings["offers_bulk_create_sec"] = 0.0
        if offers_to_update:
            bulk_update_started = time.perf_counter()
            SupplierOffer.objects.bulk_update(
                offers_to_update,
                fields=("currency", "purchase_price", "price_levels", "stock_qty", "lead_time_days", "is_available", "last_seen_at", "updated_at"),
                batch_size=1000,
            )
            updated += len(offers_to_update)
            timings["offers_bulk_update_sec"] = _elapsed_seconds(bulk_update_started)
        else:
            timings["offers_bulk_update_sec"] = 0.0
        if seen_existing_offer_ids:
            last_seen_started = time.perf_counter()
            SupplierOffer.objects.filter(id__in=seen_existing_offer_ids).update(last_seen_at=now)
            timings["offers_last_seen_update_sec"] = _elapsed_seconds(last_seen_started)
        else:
            timings["offers_last_seen_update_sec"] = 0.0
        if stale_offers_to_disable:
            stale_update_started = time.perf_counter()
            SupplierOffer.objects.bulk_update(
                stale_offers_to_disable,
                fields=("stock_qty", "is_available", "updated_at"),
                batch_size=1000,
            )
            updated += len(stale_offers_to_disable)
            timings["stale_offers_bulk_update_sec"] = _elapsed_seconds(stale_update_started)
        else:
            timings["stale_offers_bulk_update_sec"] = 0.0

        if _should_disable_missing_offers(source=source, seen_supplier_skus=seen_supplier_skus):
            disable_missing_started = time.perf_counter()
            missing_offer_ids: list[str] = []
            missing_product_ids: set[str] = set()
            available_scan_count = 0
            available_rows = SupplierOffer.objects.filter(
                supplier=source.supplier,
                is_available=True,
            ).values("id", "product_id", "supplier_sku").iterator(chunk_size=5000)
            for available in available_rows:
                available_scan_count += 1
                if available["supplier_sku"] in seen_supplier_skus:
                    continue
                missing_offer_ids.append(str(available["id"]))
                if available["product_id"]:
                    missing_product_ids.add(str(available["product_id"]))
            disabled_count = 0
            if missing_offer_ids:
                disabled_count = SupplierOffer.objects.filter(id__in=missing_offer_ids).update(
                    is_available=False,
                    stock_qty=0,
                    updated_at=now,
                )
            if disabled_count:
                updated += int(disabled_count)
                affected_products.update(missing_product_ids)
            timings["disable_missing_sec"] = _elapsed_seconds(disable_missing_started)
            timings["disable_missing_available_scanned"] = available_scan_count
            timings["disable_missing_count"] = int(disabled_count)
        else:
            timings["disable_missing_sec"] = 0.0
            timings["disable_missing_available_scanned"] = 0
            timings["disable_missing_count"] = 0

        if utr_detail_updates:
            utr_detail_started = time.perf_counter()
            _bulk_attach_utr_detail_ids(updates=utr_detail_updates)
            timings["utr_detail_attach_sec"] = _elapsed_seconds(utr_detail_started)
            timings["utr_detail_candidates"] = len(utr_detail_updates)
        else:
            timings["utr_detail_attach_sec"] = 0.0
            timings["utr_detail_candidates"] = 0

        if gpl_product_article_updates:
            article_sync_started = time.perf_counter()
            updated_article_count = _bulk_sync_gpl_product_articles(updates=gpl_product_article_updates)
            timings["gpl_product_article_sync_sec"] = _elapsed_seconds(article_sync_started)
            timings["gpl_product_article_updated"] = int(updated_article_count)
        else:
            timings["gpl_product_article_sync_sec"] = 0.0
            timings["gpl_product_article_updated"] = 0

        timings["product_i18n_bulk_update_sec"] = 0.0
        timings["product_i18n_updated_candidates"] = 0

        if is_gpl_source and affected_products:
            image_sync_started = time.perf_counter()
            image_service = GplProductImageService()
            gpl_images_created = 0
            gpl_images_reused = 0
            gpl_images_stale_marked = 0
            gpl_images_products_updated = 0
            products_qs = Product.objects.filter(id__in=list(affected_products)).only("id", "name")
            for product in products_qs.iterator(chunk_size=300):
                result = image_service.sync_product_images(product=product, dry_run=False)
                gpl_images_created += int(result.created)
                gpl_images_reused += int(result.reused)
                gpl_images_stale_marked += int(result.stale_marked)
                if int(result.created) > 0 or int(result.stale_marked) > 0:
                    gpl_images_products_updated += 1
            timings["gpl_image_sync_sec"] = _elapsed_seconds(image_sync_started)
            summary_images = {
                "products_updated": gpl_images_products_updated,
                "created": gpl_images_created,
                "reused": gpl_images_reused,
                "stale_marked": gpl_images_stale_marked,
            }
        else:
            summary_images = {
                "products_updated": 0,
                "created": 0,
                "reused": 0,
                "stale_marked": 0,
            }
            timings["gpl_image_sync_sec"] = 0.0


    return created, updated, bootstrap_products_would_reuse, summary_images, affected_products, timings
