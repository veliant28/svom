from __future__ import annotations

import time
from collections import defaultdict
from decimal import Decimal
import re

from django.conf import settings
from django.db import connections
from django.utils import timezone
from django.utils.text import slugify

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.catalog.models import Category, Product
from apps.catalog.services.product_management import generate_unique_product_slug, sanitize_product_name
from apps.catalog.services.svom_sku import ensure_product_svom_sku
from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import (
    ImportArtifact,
    ImportRowError,
    ImportRun,
    ImportSource,
    SupplierRawOffer,
)
from apps.supplier_imports.parsers import ParseResult
from apps.supplier_imports.parsers.utils import normalize_brand
from apps.supplier_imports.services.gpl_import_category_assignment import (
    MAPPING_STATUS_ASSIGNED_GROUP,
    MAPPING_STATUS_ASSIGNED_ROW,
    MAPPING_STATUS_CONFLICT,
    MAPPING_STATUS_MISSING,
)


def attach_utr_detail_id(*, product: Product, utr_detail_id: str) -> None:
    normalized = str(utr_detail_id or "").strip()
    if not normalized:
        return
    if str(product.utr_detail_id or "").strip() == normalized:
        return
    product.utr_detail_id = normalized
    product.save(update_fields=("utr_detail_id", "updated_at"))


def _bulk_attach_utr_detail_ids(*, updates: dict[str, str]) -> None:
    if not updates:
        return
    products = list(Product.objects.filter(id__in=list(updates.keys())).only("id", "utr_detail_id"))
    to_update: list[Product] = []
    for product in products:
        normalized = str(updates.get(str(product.id), "") or "").strip()
        if not normalized:
            continue
        if str(product.utr_detail_id or "").strip() == normalized:
            continue
        product.utr_detail_id = normalized
        to_update.append(product)
    if to_update:
        Product.objects.bulk_update(to_update, fields=("utr_detail_id", "updated_at"), batch_size=1000)


def _bulk_sync_gpl_product_articles(*, updates: dict[str, str]) -> int:
    if not updates:
        return 0
    products = list(Product.objects.filter(id__in=list(updates.keys())).only("id", "article"))
    to_update: list[Product] = []
    for product in products:
        next_article = str(updates.get(str(product.id), "") or "").strip()[:128]
        if not next_article:
            continue
        if str(product.article or "").strip() == next_article:
            continue
        product.article = next_article
        to_update.append(product)
    if not to_update:
        return 0
    Product.objects.bulk_update(to_update, fields=("article", "updated_at"), batch_size=1000)
    return len(to_update)


def create_row_error(
    *,
    run: ImportRun,
    source: ImportSource,
    message: str,
    artifact: ImportArtifact | None = None,
    row_number: int | None = None,
    external_sku: str = "",
    error_code: str = "import_error",
    raw_payload: dict | None = None,
) -> ImportRowError:
    return ImportRowError(
        **_row_error_kwargs(
            run=run,
            source=source,
            artifact=artifact,
            row_number=row_number,
            external_sku=external_sku,
            error_code=error_code,
            message=message,
            raw_payload=raw_payload,
        )
    )


def _build_row_error(
    *,
    run: ImportRun,
    source: ImportSource,
    message: str,
    artifact: ImportArtifact | None = None,
    row_number: int | None = None,
    external_sku: str = "",
    error_code: str = "import_error",
    raw_payload: dict | None = None,
) -> ImportRowError:
    return ImportRowError(
        **_row_error_kwargs(
            run=run,
            source=source,
            artifact=artifact,
            row_number=row_number,
            external_sku=external_sku,
            error_code=error_code,
            message=message,
            raw_payload=raw_payload,
        )
    )


def _row_error_kwargs(
    *,
    run: ImportRun,
    source: ImportSource,
    message: str,
    artifact: ImportArtifact | None = None,
    row_number: int | None = None,
    external_sku: str = "",
    error_code: str = "import_error",
    raw_payload: dict | None = None,
) -> dict:
    return {
        "run": run,
        "source": source,
        "artifact": artifact,
        "row_number": row_number,
        "external_sku": external_sku[:128],
        "error_code": error_code[:64],
        "message": message,
        "raw_payload": raw_payload or {},
    }


def _uses_current_offer_persistence(*, source: ImportSource) -> bool:
    parser_options = source.parser_options if isinstance(source.parser_options, dict) else {}
    explicit_mode = str(parser_options.get("persistence_mode") or "").strip().lower()
    if explicit_mode in {"raw", "raw_history", "history"}:
        return False
    if explicit_mode in {"current", "current_offers", "direct", "lean"}:
        return True

    current_sources = {
        str(item).strip().lower()
        for item in getattr(settings, "SUPPLIER_IMPORT_CURRENT_OFFER_SOURCES", ())
        if str(item).strip()
    }
    return source.code.lower() in current_sources


def uses_current_offer_persistence(*, source: ImportSource) -> bool:
    return _uses_current_offer_persistence(source=source)


def _cleanup_old_row_errors(*, source: ImportSource) -> dict[str, int]:
    keep_runs = _row_error_retention_runs(source=source)
    if keep_runs <= 0:
        return {
            "enabled": 0,
            "keep_runs": keep_runs,
            "deleted": 0,
        }

    retained_run_ids = list(
        ImportRun.objects.filter(source=source)
        .order_by("-started_at", "-created_at")
        .values_list("id", flat=True)[:keep_runs]
    )
    if not retained_run_ids:
        return {
            "enabled": 1,
            "keep_runs": keep_runs,
            "deleted": 0,
        }

    deleted_count, _ = ImportRowError.objects.filter(source=source).exclude(run_id__in=retained_run_ids).delete()
    return {
        "enabled": 1,
        "keep_runs": keep_runs,
        "retained_runs": len(retained_run_ids),
        "deleted": int(deleted_count),
    }


def _row_error_retention_runs(*, source: ImportSource) -> int:
    parser_options = source.parser_options if isinstance(source.parser_options, dict) else {}
    if "row_error_retention_runs" in parser_options:
        try:
            return max(int(parser_options.get("row_error_retention_runs") or 0), 0)
        except (TypeError, ValueError):
            return 0
    return max(int(getattr(settings, "SUPPLIER_IMPORT_ROW_ERROR_RETENTION_RUNS", 5)), 0)


def _elapsed_seconds(started_at: float) -> float:
    return round(time.perf_counter() - started_at, 3)


def _should_disable_missing_offers(*, source: ImportSource, seen_supplier_skus: set[str]) -> bool:
    if not seen_supplier_skus:
        return False
    parser_options = source.parser_options if isinstance(source.parser_options, dict) else {}
    raw_value = parser_options.get("disable_missing_offers", True)
    return raw_value is not False


def _should_bootstrap_unmatched_current_offers(*, source: ImportSource) -> bool:
    parser_options = source.parser_options if isinstance(source.parser_options, dict) else {}
    if "bootstrap_unmatched_products" in parser_options:
        return bool(parser_options.get("bootstrap_unmatched_products"))

    source_code = str(getattr(source, "code", "") or "").strip().lower()
    if source_code != "gpl":
        return False

    has_products = Product.objects.exists()
    has_supplier_offers = SupplierOffer.objects.filter(supplier=source.supplier).exists()
    return not has_products and not has_supplier_offers


def _should_persist_raw_rows_for_current_offers(*, source: ImportSource, bootstrap_unmatched: bool) -> bool:
    parser_options = source.parser_options if isinstance(source.parser_options, dict) else {}
    if "persist_raw_rows_current_offers" in parser_options:
        return bool(parser_options.get("persist_raw_rows_current_offers"))
    return bool(bootstrap_unmatched)


def _get_or_create_bootstrap_product_for_offer(
    *,
    source: ImportSource,
    offer,
    supplier_sku: str,
    mapped_category: Category | None = None,
    autodb_supplier_brand_lookup: dict[str, tuple[int, str]],
) -> tuple[Product, bool]:
    resolved_sku = _build_bootstrap_product_sku(source=source, supplier_sku=supplier_sku)
    raw_brand_name = sanitize_product_name(str(offer.brand_name or ""))[:120] or "UNKNOWN"
    autodb_supplier_id, autodb_supplier_name = _resolve_autodb_supplier_brand(
        raw_brand_name=raw_brand_name,
        lookup=autodb_supplier_brand_lookup,
    )
    resolved_display_brand = sanitize_product_name(autodb_supplier_name or raw_brand_name)[:255] or "UNKNOWN"
    existing = Product.objects.filter(sku=resolved_sku).first()
    if existing is not None:
        update_fields: list[str] = []
        if autodb_supplier_id and int(getattr(existing, "autodb_supplier_id", 0) or 0) != int(autodb_supplier_id):
            existing.autodb_supplier_id = int(autodb_supplier_id)
            update_fields.append("autodb_supplier_id")
        if autodb_supplier_name and str(getattr(existing, "autodb_supplier_name", "") or "").strip() != autodb_supplier_name:
            existing.autodb_supplier_name = autodb_supplier_name[:255]
            update_fields.append("autodb_supplier_name")
        if resolved_display_brand and str(getattr(existing, "display_brand_name", "") or "").strip() != resolved_display_brand:
            existing.display_brand_name = resolved_display_brand
            update_fields.append("display_brand_name")
        normalized_brand_value = normalize_brand(resolved_display_brand)[:180]
        if normalized_brand_value and str(getattr(existing, "normalized_brand", "") or "").strip() != normalized_brand_value:
            existing.normalized_brand = normalized_brand_value
            update_fields.append("normalized_brand")
        expected_brand_source = Product.BRAND_SOURCE_AUTODB_PRO if autodb_supplier_id else Product.BRAND_SOURCE_SUPPLIER_FALLBACK
        if str(getattr(existing, "brand_source", "") or "") != expected_brand_source:
            existing.brand_source = expected_brand_source
            update_fields.append("brand_source")
        if update_fields:
            existing.save(update_fields=[*update_fields, "updated_at"])
        return existing, False

    base_name = sanitize_product_name(str(offer.product_name or ""))[:255]
    if not base_name:
        base_name = sanitize_product_name(str(offer.article or offer.external_sku or supplier_sku))[:255] or "Товар без названия"
    preferred_slug = slugify(f"{base_name}-{resolved_sku}")[:300]
    now = timezone.now()
    product = Product.objects.create(
        sku=resolved_sku,
        article=str(offer.article or offer.external_sku or supplier_sku)[:128],
        name=base_name,
        name_uk=base_name,
        name_ru=base_name,
        name_en=base_name,
        slug=generate_unique_product_slug(name=base_name, preferred_slug=preferred_slug),
        brand_id=1,
        is_active=True,
        published_at=now,
        catalog_source=Product.CATALOG_SOURCE_AUTODB_PRO,
        name_source=Product.NAME_SOURCE_SUPPLIER_FALLBACK,
        name_source_text=base_name[:255],
        name_translation_status=Product.NAME_TRANSLATION_PENDING,
        autodb_supplier_id=autodb_supplier_id,
        autodb_supplier_name=autodb_supplier_name[:255],
        display_brand_name=resolved_display_brand,
        normalized_brand=normalize_brand(resolved_display_brand)[:180],
        brand_source=(Product.BRAND_SOURCE_AUTODB_PRO if autodb_supplier_id else Product.BRAND_SOURCE_SUPPLIER_FALLBACK),
        views_count=0,
        available_stock_qty_cached=0,
        category=mapped_category,
    )
    ensure_product_svom_sku(product)
    return product, True


def _build_gpl_group_decisions(
    *,
    parse_result: ParseResult,
    resolver,
) -> dict[tuple[str, str], object]:
    grouped_rows: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for offer in parse_result.offers:
        payload = _gpl_row_payload(offer=offer)
        grouped_rows[_gpl_group_key(payload=payload)].append(payload)
    out: dict[tuple[str, str], object] = {}
    for key, rows in grouped_rows.items():
        out[key] = resolver.decide_group(rows=rows)
    return out


def _gpl_group_key(*, payload: dict[str, str]) -> tuple[str, str]:
    raw_category = str(payload.get("Категорія") or payload.get("category") or "").strip()
    raw_group = str(payload.get("Група ТД") or payload.get("group") or "").strip()
    return raw_category, raw_group


def _gpl_row_payload(*, offer) -> dict[str, str]:
    payload = offer.raw_payload if isinstance(offer.raw_payload, dict) else {}
    out = {str(key): str(value) for key, value in payload.items() if key is not None}
    if not out.get("Категорія"):
        out["Категорія"] = str(payload.get("category") or payload.get("Категория") or "")
    if not out.get("Група ТД"):
        out["Група ТД"] = str(payload.get("group") or payload.get("Группа ТД") or "")
    if not out.get("Найменування"):
        out["Найменування"] = str(payload.get("name") or payload.get("title") or "")
    if not out.get("Опис"):
        out["Опис"] = str(payload.get("description") or "")
    if not out.get("Артикул ТД"):
        out["Артикул ТД"] = str(payload.get("article") or "")
    if not out.get("Артикул"):
        out["Артикул"] = str(payload.get("Артикул") or payload.get("article") or "")
    return out


def _extract_gpl_image_url(*, payload: dict[str, str]) -> str:
    candidates = (
        "Зображення товару",
        "Фото",
        "image_url",
        "image",
        "photo",
        "photo_url",
    )
    for key in candidates:
        value = str(payload.get(key) or "").strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
    return ""


def _resolve_category_mapping_reason(*, gpl_row_decision, fallback: str) -> str:
    if gpl_row_decision is None:
        if fallback == "from_product":
            return SupplierRawOffer.CATEGORY_MAPPING_REASON_FROM_PRODUCT
        return SupplierRawOffer.CATEGORY_MAPPING_REASON_NO_CATEGORY_SIGNAL
    if gpl_row_decision.mapping_status == MAPPING_STATUS_ASSIGNED_GROUP:
        return SupplierRawOffer.CATEGORY_MAPPING_REASON_SUPPLIER_CATEGORY_EXACT
    if gpl_row_decision.mapping_status == MAPPING_STATUS_ASSIGNED_ROW:
        return SupplierRawOffer.CATEGORY_MAPPING_REASON_NAME_TOKENS
    if gpl_row_decision.mapping_status == MAPPING_STATUS_CONFLICT:
        return SupplierRawOffer.CATEGORY_MAPPING_REASON_NOT_ASSIGNABLE
    if gpl_row_decision.mapping_status == MAPPING_STATUS_MISSING:
        return SupplierRawOffer.CATEGORY_MAPPING_REASON_LOW_CONFIDENCE
    return SupplierRawOffer.CATEGORY_MAPPING_REASON_NO_CATEGORY_SIGNAL


def _resolve_category_mapping_confidence(*, gpl_row_decision, fallback: Decimal | None) -> Decimal | None:
    if gpl_row_decision is None:
        return fallback
    confidence = float(getattr(gpl_row_decision, "confidence", 0.0) or 0.0)
    if confidence <= 0.0:
        return fallback
    if confidence > 1.0:
        confidence = 1.0
    return Decimal(f"{confidence:.3f}")


def _build_bootstrap_product_sku(*, source: ImportSource, supplier_sku: str) -> str:
    del source
    candidate = str(supplier_sku or "").strip()[:64]
    return candidate or "ITEM"


def _build_autodb_supplier_brand_lookup() -> dict[str, tuple[int, str]]:
    out: dict[str, tuple[int, str]] = {}
    token_candidates: dict[str, set[tuple[int, str]]] = defaultdict(set)
    try:
        alias_rows = (
            AutoDbSupplierBrandAlias.objects.filter(is_active=True)
            .order_by("-manual_confirmed", "-confidence", "id")
            .values("normalized_raw_brand", "raw_brand", "autodb_supplier_id", "autodb_supplier_name")
        )
        for row in alias_rows.iterator(chunk_size=1000):
            supplier_id = int(row.get("autodb_supplier_id") or 0)
            if supplier_id <= 0:
                continue
            alias_value = str(row.get("normalized_raw_brand") or row.get("raw_brand") or "")
            supplier_name = sanitize_product_name(str(row.get("autodb_supplier_name") or ""))[:255]
            for key in _alias_keys_for_lookup(alias_value):
                if key and key not in out:
                    out[key] = (supplier_id, supplier_name or str(supplier_id))
    except Exception:
        pass

    try:
        with connections["auto_db_pro"].cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s."id" AS supplier_id,
                    s."description" AS supplier_description,
                    s."matchcode" AS supplier_matchcode
                FROM "suppliers" s
                """
            )
            for supplier_id, supplier_description, supplier_matchcode in cursor.fetchall():
                resolved_id = int(supplier_id or 0)
                if resolved_id <= 0:
                    continue
                resolved_name = sanitize_product_name(str(supplier_description or supplier_matchcode or ""))[:255]
                if not resolved_name:
                    continue
                for key in _alias_keys_for_lookup(resolved_name):
                    if key and key not in out:
                        out[key] = (resolved_id, resolved_name)
                for key in _alias_keys_for_lookup(str(supplier_matchcode or "")):
                    if key and key not in out:
                        out[key] = (resolved_id, resolved_name)
                for token in _supplier_alias_tokens(resolved_name):
                    token_key = _normalize_brand_for_lookup(token)
                    if token_key:
                        token_candidates[token_key].add((resolved_id, resolved_name))
                for token in _supplier_alias_tokens(str(supplier_matchcode or "")):
                    token_key = _normalize_brand_for_lookup(token)
                    if token_key:
                        token_candidates[token_key].add((resolved_id, resolved_name))
    except Exception:
        # Keep import resilient even if auto_db_pro connection is unavailable.
        return out

    for token_key, candidates in token_candidates.items():
        if token_key in out:
            continue
        if len(candidates) != 1:
            continue
        resolved_id, resolved_name = next(iter(candidates))
        out[token_key] = (resolved_id, resolved_name)

    return out


def _resolve_autodb_supplier_brand(
    *,
    raw_brand_name: str,
    lookup: dict[str, tuple[int, str]],
) -> tuple[int | None, str]:
    for key in _alias_keys_for_lookup(raw_brand_name):
        if not key:
            continue
        hit = lookup.get(key)
        if hit is not None:
            supplier_id, supplier_name = hit
            return supplier_id, supplier_name
    return None, ""


def _sync_product_autodb_brand_from_offer(
    *,
    product: Product,
    raw_brand_name: str,
    lookup: dict[str, tuple[int, str]],
) -> bool:
    autodb_supplier_id, autodb_supplier_name = _resolve_autodb_supplier_brand(raw_brand_name=raw_brand_name, lookup=lookup)
    if not autodb_supplier_id:
        return False
    update_fields: list[str] = []
    if int(getattr(product, "autodb_supplier_id", 0) or 0) != int(autodb_supplier_id):
        product.autodb_supplier_id = int(autodb_supplier_id)
        update_fields.append("autodb_supplier_id")
    if autodb_supplier_name and str(getattr(product, "autodb_supplier_name", "") or "").strip() != autodb_supplier_name:
        product.autodb_supplier_name = autodb_supplier_name[:255]
        update_fields.append("autodb_supplier_name")
    resolved_display_brand = sanitize_product_name(autodb_supplier_name or raw_brand_name)[:255] or "UNKNOWN"
    if str(getattr(product, "display_brand_name", "") or "").strip() != resolved_display_brand:
        product.display_brand_name = resolved_display_brand
        update_fields.append("display_brand_name")
    normalized_brand_value = normalize_brand(resolved_display_brand)[:180]
    if str(getattr(product, "normalized_brand", "") or "").strip() != normalized_brand_value:
        product.normalized_brand = normalized_brand_value
        update_fields.append("normalized_brand")
    if str(getattr(product, "brand_source", "") or "") != Product.BRAND_SOURCE_AUTODB_PRO:
        product.brand_source = Product.BRAND_SOURCE_AUTODB_PRO
        update_fields.append("brand_source")
    if not update_fields:
        return False
    product.save(update_fields=[*update_fields, "updated_at"])
    return True


def _normalize_brand_for_lookup(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = raw.upper()
    replacements = {
        "Ä": "AE",
        "Ö": "OE",
        "Ü": "UE",
        "ẞ": "SS",
        "ß": "SS",
        "Æ": "AE",
        "Œ": "OE",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalize_brand(normalized)


def _alias_keys_for_lookup(value: str) -> set[str]:
    out: set[str] = set()
    base = _normalize_brand_for_lookup(value)
    if base:
        out.add(base)
        collapsed = base.replace("AE", "A").replace("OE", "O").replace("UE", "U")
        if collapsed:
            out.add(collapsed)
    plain = normalize_brand(str(value or ""))
    if plain:
        out.add(plain)
    return out


def _supplier_alias_tokens(value: str) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return set()
    tokens = [item for item in re.split(r"[^A-Za-z0-9А-Яа-яІіЇїЄєҐґÄÖÜẞßÆŒ]+", raw) if item]
    out: set[str] = set()
    if tokens:
        first = tokens[0].strip()
        if len(first) >= 4:
            out.add(first)
    return out


__all__ = [
    "attach_utr_detail_id",
    "_bulk_attach_utr_detail_ids",
    "_bulk_sync_gpl_product_articles",
    "create_row_error",
    "_build_row_error",
    "_row_error_kwargs",
    "_uses_current_offer_persistence",
    "uses_current_offer_persistence",
    "_cleanup_old_row_errors",
    "_row_error_retention_runs",
    "_elapsed_seconds",
    "_should_disable_missing_offers",
    "_should_bootstrap_unmatched_current_offers",
    "_should_persist_raw_rows_for_current_offers",
    "_get_or_create_bootstrap_product_for_offer",
    "_build_gpl_group_decisions",
    "_gpl_group_key",
    "_gpl_row_payload",
    "_extract_gpl_image_url",
    "_resolve_category_mapping_reason",
    "_resolve_category_mapping_confidence",
    "_build_bootstrap_product_sku",
    "_build_autodb_supplier_brand_lookup",
    "_resolve_autodb_supplier_brand",
    "_sync_product_autodb_brand_from_offer",
]
