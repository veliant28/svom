from __future__ import annotations

from typing import Any

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.catalog.models import ProductAttribute, ProductImage
from apps.catalog.models import Product
from apps.compatibility.models import ProductFitment
from apps.supplier_imports.parsers.utils import normalize_brand

from .utils import (
    iso_or_none,
    latest_evidence,
    latest_evidence_for_stage,
    money_or_blank,
    recommended_action,
    safe_str,
    supplier_display_name,
    tecdoc_status,
)


def serialize_job(job: AutoDbMatchJob) -> dict[str, Any]:
    product = job.product
    offer = job.supplier_offer
    latest = latest_evidence(job)
    price = getattr(product, "product_price", None)
    stock_qty = int(getattr(offer, "stock_qty", 0) or getattr(product, "available_stock_qty_cached", 0) or 0)
    lookup_context = _lookup_context(job)
    return {
        "id": str(job.id),
        "product": {
            "id": str(product.id),
            "sku": product.sku,
            "svom_sku": product.svom_sku or "",
            "name": product.name,
            "brand": product.display_brand_name or product.display_brand_name or product.autodb_supplier_name or "",
            "category": product.category.name if product.category_id else "",
            "is_active": bool(product.is_active),
            "autodb_supplier_id": product.autodb_supplier_id,
            "autodb_supplier_name": product.autodb_supplier_name,
            "autodb_article_number": product.autodb_article_number,
            "autodb_article_key": product.autodb_article_key,
            "supplier_codes": _product_supplier_codes(job),
        },
        "supplier_code": job.supplier_code,
        "raw_brand": job.raw_brand,
        "normalized_brand": job.normalized_brand,
        "autodb_supplier_id": job.resolved_supplier_id,
        "autodb_supplier_display": _supplier_display(job),
        "article_source": job.article_source_type,
        "article_value": job.article_value,
        "canonical_article": job.canonical_article,
        "price": money_or_blank(getattr(price, "final_price", "")),
        "currency": getattr(price, "currency", "") if price else "",
        "stock_qty": stock_qty,
        "has_product_price": price is not None,
        "tecdoc_status": tecdoc_status(job),
        "matching_status": job.status,
        "matching_status_view": _matching_status_view(job.status, lookup_context.get("lookup_bucket")),
        "lookup_origin": lookup_context.get("lookup_origin", ""),
        "lookup_method": lookup_context.get("lookup_method", ""),
        "lookup_bucket": lookup_context.get("lookup_bucket", ""),
        "manual_remote_equivalent": bool(lookup_context.get("manual_remote_equivalent", False)),
        "recommended_action": recommended_action(job.status),
        "last_evidence": {
            "stage": latest.stage if latest else "",
            "result": latest.result if latest else "",
            "reason": latest.reason if latest else job.last_error,
            "created_at": iso_or_none(latest.created_at) if latest else None,
        },
        "created_at": iso_or_none(job.created_at),
        "updated_at": iso_or_none(job.updated_at),
    }


def serialize_unlinked_product(product: Product) -> dict[str, Any]:
    return serialize_fallback_product(
        product,
        matching_status=AutoDbMatchJob.STATUS_NEW,
        tecdoc_state="unknown",
        reason="job_not_created",
    )


def serialize_fallback_product(
    product: Product,
    *,
    matching_status: str,
    tecdoc_state: str,
    reason: str = "job_not_created",
) -> dict[str, Any]:
    price = getattr(product, "product_price", None)
    supplier_codes = _product_supplier_codes_from_product(product)
    primary_supplier = supplier_codes[0] if supplier_codes else ""
    stock_qty = _product_stock_qty(product)
    display_brand = safe_str(product.display_brand_name) or safe_str(product.autodb_supplier_name)
    article_value = safe_str(product.article)
    has_link = bool(safe_str(getattr(product, "autodb_article_key", "")))
    supplier_id = int(getattr(product, "autodb_supplier_id", 0) or 0) or None
    supplier_name = safe_str(getattr(product, "autodb_supplier_name", ""))
    return {
        "id": str(product.id),
        "product": {
            "id": str(product.id),
            "sku": product.sku,
            "svom_sku": product.svom_sku or "",
            "name": product.name,
            "brand": display_brand,
            "category": product.category.name if product.category_id else "",
            "is_active": bool(product.is_active),
            "autodb_supplier_id": supplier_id,
            "autodb_supplier_name": supplier_name,
            "autodb_article_number": product.autodb_article_number,
            "autodb_article_key": product.autodb_article_key,
            "supplier_codes": supplier_codes,
        },
        "supplier_code": primary_supplier,
        "raw_brand": display_brand,
        "normalized_brand": normalize_brand(display_brand),
        "autodb_supplier_id": supplier_id,
        "autodb_supplier_display": supplier_name if has_link else "",
        "article_source": "product_article",
        "article_value": article_value,
        "canonical_article": article_value,
        "price": money_or_blank(getattr(price, "final_price", "")),
        "currency": getattr(price, "currency", "") if price else "",
        "stock_qty": stock_qty,
        "has_product_price": price is not None,
        "tecdoc_status": tecdoc_state,
        "matching_status": matching_status,
        "matching_status_view": matching_status,
        "lookup_origin": "",
        "lookup_method": "",
        "lookup_bucket": "",
        "manual_remote_equivalent": False,
        "recommended_action": "already_linked" if has_link else "run_local_dry_run",
        "last_evidence": {
            "stage": "",
            "result": "",
            "reason": reason,
            "created_at": None,
        },
        "created_at": iso_or_none(product.created_at),
        "updated_at": iso_or_none(product.updated_at),
    }


def serialize_unlinked_product_detail(product: Product) -> dict[str, Any]:
    payload = serialize_fallback_product_detail(
        product,
        matching_status=AutoDbMatchJob.STATUS_NEW,
        tecdoc_state="unknown",
        reason="job_not_created",
    )
    return payload


def serialize_fallback_product_detail(
    product: Product,
    *,
    matching_status: str,
    tecdoc_state: str,
    reason: str = "job_not_created",
) -> dict[str, Any]:
    payload = serialize_fallback_product(
        product,
        matching_status=matching_status,
        tecdoc_state=tecdoc_state,
        reason=reason,
    )
    payload["drawer"] = {
        "product_info": {
            "sku": product.sku,
            "svom_sku": product.svom_sku or "",
            "name": product.name,
            "brand": payload["product"]["brand"],
            "category": product.category.name if product.category_id else "",
            "active": bool(product.is_active),
            "price": payload["price"],
            "currency": payload["currency"],
            "stock_qty": payload["stock_qty"],
        },
        "brand_resolution": {
            "raw_brand": payload["raw_brand"],
            "normalized_brand": payload["normalized_brand"],
            "autodb_supplier_candidate": "",
            "resolver_source": "no_job_fallback",
        },
        "article_source": {
            "selected_article_field": payload["article_value"],
            "source_type": payload["article_source"],
            "confidence": "",
            "reason": "job_not_created",
            "canonical_article": payload["canonical_article"],
        },
        "local_lookup_evidence": {},
        "remote_lookup_evidence": {},
        "clone_sync_state": {},
        "link_audit_result": {},
        "enrichment_availability": {
            "attributes_count": ProductAttribute.objects.filter(product=product).count(),
            "fitments_count": ProductFitment.objects.filter(product=product).count(),
            "images_count_preview_only": ProductImage.objects.filter(product=product).count(),
        },
        "evidence": [],
    }
    return payload


def serialize_job_detail(job: AutoDbMatchJob) -> dict[str, Any]:
    payload = serialize_job(job)
    product = job.product
    offer = job.supplier_offer
    evidence_rows = list(job.evidence.order_by("-created_at")[:30])
    payload["drawer"] = {
        "product_info": {
            "sku": product.sku,
            "svom_sku": product.svom_sku or "",
            "name": product.name,
            "brand": product.display_brand_name or product.display_brand_name or product.autodb_supplier_name or "",
            "category": product.category.name if product.category_id else "",
            "active": bool(product.is_active),
            "price": payload["price"],
            "currency": payload["currency"],
            "stock_qty": int(getattr(offer, "stock_qty", 0) or getattr(product, "available_stock_qty_cached", 0) or 0),
        },
        "brand_resolution": {
            "raw_brand": job.raw_brand,
            "normalized_brand": job.normalized_brand,
            "autodb_supplier_candidate": payload["autodb_supplier_display"],
            "resolver_source": safe_str(job.metadata_json.get("resolver_source")) or safe_str(job.metadata_json.get("brand_decision")),
        },
        "article_source": {
            "selected_article_field": job.article_value,
            "source_type": job.article_source_type,
            "confidence": job.metadata_json.get("article_confidence", ""),
            "reason": job.metadata_json.get("article_reason", job.last_error),
            "canonical_article": job.canonical_article,
        },
        "local_lookup_evidence": evidence_payload(latest_evidence_for_stage(job, "local_lookup")),
        "remote_lookup_evidence": evidence_payload(latest_evidence_for_stage(job, "remote_lookup")),
        "clone_sync_state": evidence_payload(latest_evidence_for_stage(job, "clone_sync_plan")),
        "link_audit_result": evidence_payload(latest_evidence_for_stage(job, "link_audit")),
        "enrichment_availability": {
            "attributes_count": ProductAttribute.objects.filter(product=product).count(),
            "fitments_count": ProductFitment.objects.filter(product=product).count(),
            "images_count_preview_only": ProductImage.objects.filter(product=product).count(),
        },
        "evidence": [evidence_payload(item) for item in evidence_rows],
    }
    return payload


def evidence_payload(evidence: AutoDbMatchEvidence | None) -> dict[str, Any]:
    if evidence is None:
        return {}
    return {
        "id": str(evidence.id),
        "stage": evidence.stage,
        "source": evidence.source,
        "result": evidence.result,
        "supplier_id": evidence.supplier_id,
        "article_value": evidence.article_value,
        "canonical_article": evidence.canonical_article,
        "remote_stored_article": evidence.remote_stored_article,
        "article_prd_present": evidence.article_prd_present,
        "prd_present": evidence.prd_present,
        "reason": evidence.reason,
        "payload": evidence.payload_json,
        "created_at": iso_or_none(evidence.created_at),
    }


def _supplier_display(job: AutoDbMatchJob) -> str:
    return supplier_display_name(job.resolved_supplier_id)


def _product_supplier_codes(job: AutoDbMatchJob) -> list[str]:
    codes: list[str] = []
    try:
        offers = list(job.product.supplier_offers.all())
    except Exception:  # noqa: BLE001
        offers = []
    for offer in offers:
        code = safe_str(getattr(getattr(offer, "supplier", None), "code", "")).lower()
        if code and code not in codes:
            codes.append(code)
    if not codes:
        fallback = safe_str(job.supplier_code).lower()
        if fallback:
            codes.append(fallback)
    return codes


def _product_supplier_codes_from_product(product: Product) -> list[str]:
    codes: list[str] = []
    try:
        offers = list(product.supplier_offers.all())
    except Exception:  # noqa: BLE001
        offers = []
    for offer in offers:
        code = safe_str(getattr(getattr(offer, "supplier", None), "code", "")).lower()
        if code and code not in codes:
            codes.append(code)
    return codes


def _product_stock_qty(product: Product) -> int:
    try:
        offers = list(product.supplier_offers.all())
    except Exception:  # noqa: BLE001
        offers = []
    supplier_max = 0
    for offer in offers:
        qty = int(getattr(offer, "stock_qty", 0) or 0)
        if qty > supplier_max:
            supplier_max = qty
    return max(int(getattr(product, "available_stock_qty_cached", 0) or 0), supplier_max)


def _lookup_context(job: AutoDbMatchJob) -> dict[str, Any]:
    evidence = latest_evidence_for_stage(job, "remote_lookup")
    if evidence is None:
        return {
            "lookup_origin": "",
            "lookup_method": "",
            "lookup_bucket": "",
            "manual_remote_equivalent": False,
        }
    payload = evidence.payload_json if isinstance(evidence.payload_json, dict) else {}
    raw_source = safe_str(payload.get("matched_source"))
    if not raw_source:
        return {
            "lookup_origin": "",
            "lookup_method": "",
            "lookup_bucket": "",
            "manual_remote_equivalent": False,
        }
    chunks = raw_source.split(":", 2)
    method = safe_str(chunks[0]).lower() if chunks else ""
    origin = safe_str(chunks[1]).lower() if len(chunks) > 1 else ""
    bucket = _lookup_bucket(method=method, origin=origin)
    return {
        "lookup_origin": origin,
        "lookup_method": method,
        "lookup_bucket": bucket,
        "manual_remote_equivalent": origin == "remote" and bucket == "remote_brand_exact",
    }


def _lookup_bucket(*, method: str, origin: str) -> str:
    if origin == "local":
        return "local_clone_hit"
    if origin != "remote":
        return ""
    if method.startswith("a_supplier_norm") or method.endswith("_supplier_exact"):
        return "remote_brand_exact"
    if method.endswith("_article_only"):
        return "remote_article_only"
    return "remote_other"


def _matching_status_view(status: str, lookup_bucket: str | None) -> str:
    if status != AutoDbMatchJob.STATUS_REMOTE_FOUND:
        return status
    bucket = safe_str(lookup_bucket).lower()
    if bucket == "local_clone_hit":
        return "remote_found_local_clone"
    if bucket == "remote_brand_exact":
        return "remote_found_exact"
    if bucket == "remote_article_only":
        return "remote_found_article_only"
    if bucket == "remote_other":
        return "remote_found_other"
    return status
