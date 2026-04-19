from __future__ import annotations

from apps.autocatalog.models import UtrArticleDetailMap
from apps.supplier_imports.models import SupplierRawOffer

from .normalizers import normalize_article_value, normalize_brand_value


def collect_article_brand_pairs(
    *,
    limit: int | None,
    offset: int,
    exclude_existing: bool,
) -> list[dict[str, str]]:
    existing_keys: set[tuple[str, str]] = set()
    if exclude_existing:
        existing_keys = set(
            UtrArticleDetailMap.objects.values_list(
                "normalized_article",
                "normalized_brand",
            )
        )

    queryset = (
        SupplierRawOffer.objects.filter(source__code="utr")
        .exclude(external_sku="")
        .values("external_sku", "article", "brand_name")
        .distinct()
        .order_by("external_sku", "article", "brand_name")
    )

    pairs: list[dict[str, str]] = []
    seen_keys: set[tuple[str, str]] = set()
    skipped = 0
    for row in queryset.iterator(chunk_size=2000):
        article = str(row.get("external_sku") or "").strip()
        if not article:
            continue

        normalized_article = normalize_article_value(article)
        if not normalized_article:
            continue

        brand_name = str(row.get("brand_name") or "").strip()
        normalized_brand = normalize_brand_value(brand_name)
        key = (normalized_article, normalized_brand)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        if exclude_existing and key in existing_keys:
            continue
        if skipped < offset:
            skipped += 1
            continue

        fallback_article = str(row.get("article") or "").strip()
        pairs.append(
            {
                "article": article,
                "fallback_article": fallback_article,
                "normalized_article": normalized_article,
                "brand_name": brand_name,
                "normalized_brand": normalized_brand,
            }
        )
        if limit and limit > 0 and len(pairs) >= limit:
            break
    return pairs


def collect_unresolved_pairs(*, limit: int | None, offset: int) -> list[dict[str, str]]:
    queryset = (
        UtrArticleDetailMap.objects.filter(utr_detail_id="")
        .values("article", "brand_name", "normalized_article", "normalized_brand")
        .order_by("normalized_article", "normalized_brand")
    )
    if offset > 0:
        queryset = queryset[offset:]
    if limit and limit > 0:
        queryset = queryset[:limit]

    pairs: list[dict[str, str]] = []
    for row in queryset:
        article = str(row.get("article") or "").strip()
        normalized_article = str(row.get("normalized_article") or "").strip()
        if not article or not normalized_article:
            continue
        brand_name = str(row.get("brand_name") or "").strip()
        pairs.append(
            {
                "article": article,
                "fallback_article": "",
                "normalized_article": normalized_article,
                "brand_name": brand_name,
                "normalized_brand": str(row.get("normalized_brand") or "").strip(),
            }
        )
    return pairs


def count_raw_pairs() -> int:
    queryset = (
        SupplierRawOffer.objects.filter(source__code="utr")
        .exclude(external_sku="")
        .values("external_sku", "brand_name")
        .distinct()
        .order_by("external_sku", "brand_name")
    )
    seen_keys: set[tuple[str, str]] = set()
    for row in queryset.iterator(chunk_size=2000):
        article = str(row.get("external_sku") or "").strip()
        if not article:
            continue
        normalized_article = normalize_article_value(article)
        if not normalized_article:
            continue
        brand_name = str(row.get("brand_name") or "").strip()
        key = (normalized_article, normalize_brand_value(brand_name))
        seen_keys.add(key)
    return len(seen_keys)


def build_search_stages(
    *,
    pair: dict[str, str],
    resolve_stage_order: str,
    stage_brandless_first: str,
    stage_branded_first: str,
) -> list[dict[str, str]]:
    article = str(pair.get("article") or "").strip()
    fallback_article = str(pair.get("fallback_article") or "").strip()
    brand = str(pair.get("brand_name") or "").strip()
    normalized_article = str(pair.get("normalized_article") or "").strip()
    normalized_fallback_article = normalize_article_value(fallback_article)
    has_fallback = bool(fallback_article and normalized_fallback_article and fallback_article != article)

    primary_brandless = {
        "name": "primary_brandless",
        "oem": article,
        "brand": "",
        "normalized_article": normalized_article,
    }
    fallback_brandless = {
        "name": "fallback_brandless",
        "oem": fallback_article,
        "brand": "",
        "normalized_article": normalized_fallback_article,
    }
    primary_branded = {
        "name": "primary_branded",
        "oem": article,
        "brand": brand,
        "normalized_article": normalized_article,
    }
    fallback_branded = {
        "name": "fallback_branded",
        "oem": fallback_article,
        "brand": brand,
        "normalized_article": normalized_fallback_article,
    }

    stages: list[dict[str, str]] = []
    if resolve_stage_order == stage_branded_first and brand:
        stages.append(primary_branded)
        if has_fallback:
            stages.append(fallback_branded)
        stages.append(primary_brandless)
        if has_fallback:
            stages.append(fallback_brandless)
        return stages

    stages.append(primary_brandless)
    if has_fallback:
        stages.append(fallback_brandless)
    if brand:
        stages.append(primary_branded)
        if has_fallback:
            stages.append(fallback_branded)
    return stages


def collect_stage_queries(
    *,
    contexts,
    stage_index: int,
    search_cache: dict[tuple[str, str], list[dict]],
    search_query_outcomes: dict[tuple[str, str], dict],
) -> list[dict[str, str]]:
    seen_keys: set[tuple[str, str]] = set()
    queries: list[dict[str, str]] = []
    for context in contexts:
        query = context.stages[stage_index]
        oem = str(query.get("oem") or "").strip()
        brand = str(query.get("brand") or "").strip()
        if not oem:
            continue
        key = (oem, brand)
        if key in seen_keys or key in search_cache or key in search_query_outcomes:
            continue
        seen_keys.add(key)
        queries.append({"oem": oem, "brand": brand})
    return queries


def build_batch_payload_item(*, query: dict[str, str]) -> dict[str, str]:
    payload = {"oem": str(query.get("oem") or "").strip()}
    brand = str(query.get("brand") or "").strip()
    if brand:
        payload["brand"] = brand
    return payload
