from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.cache import cache

from apps.autodb.models import (
    AutoDbArticleAttribute,
    AutoDbArticleImage,
    AutoDbArticleProductGroup,
    AutoDbProductGroup,
    AutoDbSupplier,
)
from apps.catalog.models import Product
from apps.catalog.services.category_management import normalized_category_name
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand

try:
    import mysql.connector
except Exception:  # noqa: BLE001
    mysql = None
else:
    mysql = mysql.connector

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AutoDbProductContent:
    image_urls: list[str]
    attributes: list[dict[str, str]]
    product_groups: list[dict[str, str | int]]


def get_autodb_product_content(*, product: Product, prefer_live: bool = True) -> AutoDbProductContent:
    cache_key = f"autodb:content:product:{product.id}:live:{int(prefer_live)}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return AutoDbProductContent(
            image_urls=list(cached.get("image_urls") or []),
            attributes=list(cached.get("attributes") or []),
            product_groups=list(cached.get("product_groups") or []),
        )

    pairs = _resolve_article_brand_pairs(product=product)
    if not pairs:
        return AutoDbProductContent(image_urls=[], attributes=[], product_groups=[])

    supplier_ids = _resolve_supplier_ids(pairs=pairs)
    if not supplier_ids:
        return AutoDbProductContent(image_urls=[], attributes=[], product_groups=[])

    articles = {article for article, _brand in pairs}

    if prefer_live and bool(getattr(settings, "AUTODB_LIVE_CONTENT_ENABLED", True)):
        try:
            _refresh_cache_from_live(supplier_ids=supplier_ids, articles=articles)
        except Exception as exc:  # noqa: BLE001
            logger.warning("autodb_live_content_refresh_failed product_id=%s error=%s", product.id, exc)

    content = _build_content_from_cache(supplier_ids=supplier_ids, articles=articles)
    cache.set(
        cache_key,
        {
            "image_urls": content.image_urls,
            "attributes": content.attributes,
            "product_groups": content.product_groups,
        },
        timeout=max(int(getattr(settings, "AUTODB_CONTENT_CACHE_TTL_SECONDS", 60 * 30)), 30),
    )
    return content


def get_autodb_primary_image_url(*, product: Product) -> str:
    content = get_autodb_product_content(product=product, prefer_live=False)
    if not content.image_urls:
        return ""
    return content.image_urls[0]


def build_autodb_characteristic_attributes(*, product: Product) -> list[dict[str, str]]:
    content = get_autodb_product_content(product=product, prefer_live=True)
    rows: list[dict[str, str]] = []
    for index, item in enumerate(content.attributes):
        name = str(item.get("attribute_name") or "").strip()
        value = str(item.get("value") or "").strip()
        if not name or not value:
            continue
        rows.append(
            {
                "id": f"autodb-{product.id}-{index}",
                "attribute_name": name,
                "value": value,
            }
        )
    return rows


def resolve_autodb_category_candidates(*, product: Product) -> list[dict[str, str | int]]:
    content = get_autodb_product_content(product=product, prefer_live=True)
    return content.product_groups


def resolve_autodb_article_name(
    *,
    normalized_article: str,
    normalized_brand: str,
    prefer_live: bool = True,
) -> str:
    article_raw = str(normalized_article or "").strip()
    article = normalize_article(article_raw)
    brand = normalize_brand(normalized_brand)
    if not article or not brand:
        return ""

    cache_key = f"autodb:name:{brand}:{article}:live:{int(prefer_live)}"
    cached = cache.get(cache_key)
    if isinstance(cached, str):
        return cached

    if prefer_live and bool(getattr(settings, "AUTODB_LIVE_CONTENT_ENABLED", True)):
        try:
            name = _load_article_name_from_live(
                article_candidates=_build_article_candidates(article_raw=article_raw, normalized_article=article),
                normalized_brand=brand,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("autodb_live_name_refresh_failed article=%s brand=%s error=%s", article, brand, exc)
            name = ""
    else:
        name = ""

    cache.set(
        cache_key,
        name,
        timeout=max(int(getattr(settings, "AUTODB_CONTENT_CACHE_TTL_SECONDS", 60 * 30)), 30),
    )
    return name


def _build_content_from_cache(*, supplier_ids: set[int], articles: set[str]) -> AutoDbProductContent:
    image_rows = (
        AutoDbArticleImage.objects.filter(
            supplier_id__in=sorted(supplier_ids),
            normalized_article__in=sorted(articles),
        )
        .order_by("-is_primary", "sort_order", "id")
        .values_list("image_url", "image_path")
    )
    image_urls: list[str] = []
    seen_images: set[str] = set()
    for image_url, image_path in image_rows:
        url = _normalize_image_url(image_url=image_url, image_path=image_path)
        if not url or url in seen_images:
            continue
        seen_images.add(url)
        image_urls.append(url)
        if len(image_urls) >= 12:
            break

    attribute_rows = (
        AutoDbArticleAttribute.objects.filter(
            supplier_id__in=sorted(supplier_ids),
            normalized_article__in=sorted(articles),
        )
        .order_by("sort_order", "attribute_name", "id")
        .values_list("attribute_name", "attribute_value", "unit")
    )
    attributes: list[dict[str, str]] = []
    seen_attr: set[tuple[str, str]] = set()
    for name, value, unit in attribute_rows:
        clean_name = str(name or "").strip()
        clean_value = str(value or "").strip()
        clean_unit = str(unit or "").strip()
        if not clean_name or not clean_value:
            continue
        if clean_unit:
            clean_value = f"{clean_value} {clean_unit}".strip()
        key = (clean_name.lower(), clean_value.lower())
        if key in seen_attr:
            continue
        seen_attr.add(key)
        attributes.append({"attribute_name": clean_name, "value": clean_value})

    group_rows = (
        AutoDbArticleProductGroup.objects.filter(
            supplier_id__in=sorted(supplier_ids),
            normalized_article__in=sorted(articles),
        )
        .select_related("product_group")
        .order_by("product_group_id")
    )
    product_groups: list[dict[str, str | int]] = []
    seen_group: set[int] = set()
    for row in group_rows:
        group_id = int(row.product_group_id)
        if group_id in seen_group:
            continue
        seen_group.add(group_id)
        group = row.product_group
        product_groups.append(
            {
                "prd_id": group_id,
                "prd_name": str(group.name or "").strip(),
            }
        )

    return AutoDbProductContent(
        image_urls=image_urls,
        attributes=attributes,
        product_groups=product_groups,
    )


def _refresh_cache_from_live(*, supplier_ids: set[int], articles: set[str]) -> None:
    if mysql is None:
        return

    cfg = {
        "host": str(getattr(settings, "AUTODB_SOURCE_MYSQL_HOST", "")).strip(),
        "database": str(getattr(settings, "AUTODB_SOURCE_MYSQL_DATABASE", "")).strip(),
        "user": str(getattr(settings, "AUTODB_SOURCE_MYSQL_USER", "")).strip(),
        "password": str(getattr(settings, "AUTODB_SOURCE_MYSQL_PASSWORD", "") or ""),
        "connection_timeout": int(getattr(settings, "AUTODB_SOURCE_MYSQL_TIMEOUT_SECONDS", 10)),
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    if not cfg["host"] or not cfg["database"] or not cfg["user"]:
        return

    source = mysql.connect(**cfg)
    try:
        columns_by_table = {
            "article_images": _table_columns(source=source, table="article_images"),
            "article_attributes": _table_columns(source=source, table="article_attributes"),
            "article_prd": _table_columns(source=source, table="article_prd"),
            "prd": _table_columns(source=source, table="prd"),
        }

        _refresh_images_from_live(
            source=source,
            supplier_ids=supplier_ids,
            articles=articles,
            columns=columns_by_table["article_images"],
        )
        _refresh_attributes_from_live(
            source=source,
            supplier_ids=supplier_ids,
            articles=articles,
            columns=columns_by_table["article_attributes"],
        )
        _refresh_groups_from_live(
            source=source,
            supplier_ids=supplier_ids,
            articles=articles,
            article_prd_columns=columns_by_table["article_prd"],
            prd_columns=columns_by_table["prd"],
        )
    finally:
        source.close()


def _load_article_name_from_live(*, article_candidates: set[str], normalized_brand: str) -> str:
    if mysql is None:
        return ""

    cfg = {
        "host": str(getattr(settings, "AUTODB_SOURCE_MYSQL_HOST", "")).strip(),
        "database": str(getattr(settings, "AUTODB_SOURCE_MYSQL_DATABASE", "")).strip(),
        "user": str(getattr(settings, "AUTODB_SOURCE_MYSQL_USER", "")).strip(),
        "password": str(getattr(settings, "AUTODB_SOURCE_MYSQL_PASSWORD", "") or ""),
        "connection_timeout": int(getattr(settings, "AUTODB_SOURCE_MYSQL_TIMEOUT_SECONDS", 10)),
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    if not cfg["host"] or not cfg["database"] or not cfg["user"]:
        return ""

    source = mysql.connect(**cfg)
    try:
        supplier_ids = _fetch_supplier_ids_from_live(source=source, normalized_brand=normalized_brand)
        if not supplier_ids or not article_candidates:
            return ""

        supplier_placeholders = ", ".join(["%s"] * len(supplier_ids))
        article_placeholders = ", ".join(["%s"] * len(article_candidates))
        sql = (
            "SELECT InformationText, InformationType "
            "FROM article_inf "
            f"WHERE supplierId IN ({supplier_placeholders}) "
            f"AND DataSupplierArticleNumber IN ({article_placeholders})"
        )
        params = (*sorted(supplier_ids), *sorted(article_candidates))
        cursor = source.cursor()
        try:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return _pick_best_article_name(rows)
    finally:
        source.close()


def _refresh_images_from_live(*, source, supplier_ids: set[int], articles: set[str], columns: list[str]) -> None:
    supplier_col = _pick_column(columns, ("supplierId", "sup_id", "ART_SUP_ID", "BrandNo"))
    article_col = _pick_column(columns, ("DataSupplierArticleNumber", "articleNumber", "ART_ARTICLE_NR", "ArtNo"))
    if not supplier_col or not article_col:
        return

    image_url_col = _pick_column(columns, ("fullImagePath", "imageUrl", "url", "image"))
    image_path_col = _pick_column(columns, ("imagePath", "path", "filePath", "file"))
    extension_col = _pick_column(columns, ("extension", "fileExt", "imageExt", "fileExtension", "type"))
    primary_col = _pick_column(columns, ("isPrimary", "primary", "isMain", "main"))
    sort_col = _pick_column(columns, ("sortOrder", "sort", "position", "seqNo", "orderNo"))
    image_url_expr = image_url_col or "''"
    image_path_expr = image_path_col or "''"
    extension_expr = extension_col or "''"
    primary_expr = primary_col or "0"
    sort_expr = sort_col or "0"

    select_sql = (
        f"SELECT {supplier_col}, {article_col}, "
        f"{image_url_expr}, "
        f"{image_path_expr}, "
        f"{extension_expr}, "
        f"{primary_expr}, "
        f"{sort_expr} "
        "FROM article_images"
    )
    rows = _fetch_rows(source=source, sql=select_sql, supplier_col=supplier_col, article_col=article_col, supplier_ids=supplier_ids, articles=articles)

    payload: list[AutoDbArticleImage] = []
    for row in rows:
        supplier_id = _to_int(row[0])
        article_number = str(row[1] or "").strip()
        if not supplier_id or not article_number:
            continue
        image_url = str(row[2] or "").strip()
        image_path = str(row[3] or "").strip()
        if not image_url and not image_path:
            continue
        payload.append(
            AutoDbArticleImage(
                supplier_id=supplier_id,
                article_number=article_number,
                normalized_article=normalize_article(article_number),
                image_url=image_url,
                image_path=image_path,
                file_extension=str(row[4] or "").strip()[:16],
                is_primary=_to_bool(row[5]),
                sort_order=_to_int(row[6], default=0) or 0,
            )
        )
    if payload:
        AutoDbArticleImage.objects.bulk_create(payload, ignore_conflicts=True, batch_size=1000)


def _refresh_attributes_from_live(*, source, supplier_ids: set[int], articles: set[str], columns: list[str]) -> None:
    supplier_col = _pick_column(columns, ("supplierId", "sup_id", "ART_SUP_ID", "BrandNo"))
    article_col = _pick_column(columns, ("DataSupplierArticleNumber", "articleNumber", "ART_ARTICLE_NR", "ArtNo"))
    name_col = _pick_column(columns, ("attributeName", "name", "title", "criterionName", "criteriaName"))
    value_col = _pick_column(columns, ("attributeValue", "value", "criterionValue", "criteriaValue"))
    if not supplier_col or not article_col or not name_col:
        return

    unit_col = _pick_column(columns, ("unit", "measureUnit", "uom"))
    sort_col = _pick_column(columns, ("sortOrder", "sort", "position", "seqNo", "orderNo"))
    value_expr = value_col or "''"
    unit_expr = unit_col or "''"
    sort_expr = sort_col or "0"

    select_sql = (
        f"SELECT {supplier_col}, {article_col}, {name_col}, {value_expr}, "
        f"{unit_expr}, {sort_expr} "
        "FROM article_attributes"
    )
    rows = _fetch_rows(source=source, sql=select_sql, supplier_col=supplier_col, article_col=article_col, supplier_ids=supplier_ids, articles=articles)

    payload: list[AutoDbArticleAttribute] = []
    for row in rows:
        supplier_id = _to_int(row[0])
        article_number = str(row[1] or "").strip()
        attr_name = str(row[2] or "").strip()
        if not supplier_id or not article_number or not attr_name:
            continue
        payload.append(
            AutoDbArticleAttribute(
                supplier_id=supplier_id,
                article_number=article_number,
                normalized_article=normalize_article(article_number),
                attribute_name=attr_name[:255],
                attribute_value=str(row[3] or "").strip(),
                unit=str(row[4] or "").strip()[:64],
                sort_order=_to_int(row[5], default=0) or 0,
            )
        )
    if payload:
        AutoDbArticleAttribute.objects.bulk_create(payload, ignore_conflicts=True, batch_size=1000)


def _refresh_groups_from_live(
    *,
    source,
    supplier_ids: set[int],
    articles: set[str],
    article_prd_columns: list[str],
    prd_columns: list[str],
) -> None:
    supplier_col = _pick_column(article_prd_columns, ("supplierId", "sup_id", "ART_SUP_ID", "BrandNo"))
    article_col = _pick_column(article_prd_columns, ("DataSupplierArticleNumber", "articleNumber", "ART_ARTICLE_NR", "ArtNo"))
    group_col = _pick_column(article_prd_columns, ("prdId", "productId", "groupId", "PT_ID", "GenArtNo"))
    if not supplier_col or not article_col or not group_col:
        return

    select_sql = f"SELECT {supplier_col}, {article_col}, {group_col} FROM article_prd"
    rows = _fetch_rows(source=source, sql=select_sql, supplier_col=supplier_col, article_col=article_col, supplier_ids=supplier_ids, articles=articles)

    group_ids: set[int] = set()
    links: list[AutoDbArticleProductGroup] = []
    for row in rows:
        supplier_id = _to_int(row[0])
        article_number = str(row[1] or "").strip()
        group_id = _to_int(row[2])
        if not supplier_id or not article_number or not group_id:
            continue
        group_ids.add(group_id)
        links.append(
            AutoDbArticleProductGroup(
                supplier_id=supplier_id,
                article_number=article_number,
                normalized_article=normalize_article(article_number),
                product_group_id=group_id,
            )
        )

    if group_ids:
        group_id_col = _pick_column(prd_columns, ("id", "prdId", "productId", "PT_ID"))
        group_name_col = _pick_column(prd_columns, ("description", "name", "title", "text", "PT_TEXT", "fullDescription"))
        if group_id_col:
            placeholders = ", ".join(["%s"] * len(group_ids))
            group_name_expr = group_name_col or "''"
            sql = f"SELECT {group_id_col}, {group_name_expr} FROM prd WHERE {group_id_col} IN ({placeholders})"
            cursor = source.cursor()
            try:
                cursor.execute(sql, tuple(sorted(group_ids)))
                groups = cursor.fetchall()
            finally:
                cursor.close()
            payload_groups = []
            for group_id, group_name in groups:
                parsed_id = _to_int(group_id)
                if not parsed_id:
                    continue
                clean_name = str(group_name or "").strip()
                payload_groups.append(
                    AutoDbProductGroup(
                        id=parsed_id,
                        name=clean_name[:255],
                        normalized_name=normalized_category_name(clean_name)[:255],
                    )
                )
            if payload_groups:
                AutoDbProductGroup.objects.bulk_create(payload_groups, ignore_conflicts=True, batch_size=1000)

    if links:
        AutoDbArticleProductGroup.objects.bulk_create(links, ignore_conflicts=True, batch_size=1000)


def _pick_best_article_name(rows: list[tuple[Any, ...]]) -> str:
    best_text = ""
    best_score = -1
    for info_type, info_text in rows:
        clean_text = _normalize_article_info_text(info_text)
        if not clean_text:
            continue
        clean_type = str(info_type or "").strip().lower()
        score = 0
        if any(token in clean_type for token in ("name", "title", "designation", "article")):
            score += 10
        if len(clean_text) <= 140:
            score += 4
        elif len(clean_text) <= 255:
            score += 3
        elif len(clean_text) <= 500:
            score += 1

        if score > best_score:
            best_score = score
            best_text = clean_text

    return best_text[:255]


def _build_article_candidates(*, article_raw: str, normalized_article: str) -> set[str]:
    candidates: set[str] = set()
    raw = str(article_raw or "").strip()
    if raw:
        candidates.add(raw)
    if normalized_article:
        candidates.add(normalized_article)
    compact = "".join(ch for ch in raw if ch.isalnum()).strip()
    if compact:
        candidates.add(compact)
    return {value[:128] for value in candidates if value}


def _fetch_supplier_ids_from_live(*, source, normalized_brand: str) -> set[int]:
    if not normalized_brand:
        return set()
    brand_value = normalized_brand.strip().upper()
    sql = (
        "SELECT id FROM suppliers "
        "WHERE UPPER(TRIM(matchcode)) = %s OR UPPER(TRIM(description)) = %s"
    )
    cursor = source.cursor()
    try:
        cursor.execute(sql, (brand_value, brand_value))
        rows = cursor.fetchall()
    finally:
        cursor.close()
    return {int(row[0]) for row in rows if row and row[0] is not None}


def _fetch_rows(
    *,
    source,
    sql: str,
    supplier_col: str,
    article_col: str,
    supplier_ids: set[int],
    articles: set[str],
) -> list[tuple[Any, ...]]:
    if not supplier_ids or not articles:
        return []

    supplier_placeholders = ", ".join(["%s"] * len(supplier_ids))
    article_placeholders = ", ".join(["%s"] * len(articles))
    sql = (
        f"{sql} "
        f"WHERE {supplier_col} IN ({supplier_placeholders}) "
        f"AND {article_col} IN ({article_placeholders})"
    )
    params = (*sorted(supplier_ids), *sorted(articles))
    cursor = source.cursor()
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()


def _table_columns(*, source, table: str) -> list[str]:
    cursor = source.cursor()
    try:
        cursor.execute(f"SHOW COLUMNS FROM {table}")
        return [str(row[0]) for row in cursor.fetchall()]
    except Exception:
        return []
    finally:
        cursor.close()


def _pick_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    by_lower = {value.lower(): value for value in columns}
    for candidate in candidates:
        actual = by_lower.get(candidate.lower())
        if actual:
            return actual
    return None


def _resolve_article_brand_pairs(*, product: Product) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    fallback_brand = normalize_brand(getattr(product.brand, "name", ""))

    product_article = normalize_article(product.article)
    if product_article and fallback_brand:
        pairs.add((product_article, fallback_brand))

    raw_offers = (
        SupplierRawOffer.objects.filter(matched_product_id=product.id)
        .exclude(normalized_article="")
        .values_list("normalized_article", "normalized_brand")
        .distinct()
    )
    for article, brand in raw_offers:
        normalized_article = str(article or "").strip()
        if not normalized_article:
            continue
        normalized_brand = str(brand or "").strip() or fallback_brand
        if not normalized_brand:
            continue
        pairs.add((normalized_article, normalized_brand))
    return pairs


def _resolve_supplier_ids(*, pairs: set[tuple[str, str]]) -> set[int]:
    brands = sorted({brand for _article, brand in pairs if brand})
    if not brands:
        return set()
    supplier_rows = AutoDbSupplier.objects.filter(
        normalized_matchcode__in=brands,
    ).values_list("id", flat=True)
    by_match = {int(value) for value in supplier_rows}

    supplier_rows = AutoDbSupplier.objects.filter(
        normalized_name__in=brands,
    ).values_list("id", flat=True)
    by_name = {int(value) for value in supplier_rows}

    return by_match | by_name


def _normalize_image_url(*, image_url: Any, image_path: Any) -> str:
    direct = str(image_url or "").strip()
    if direct.startswith("http://") or direct.startswith("https://"):
        return direct

    raw_path = str(image_path or "").strip() or direct
    if not raw_path:
        return ""

    base_url = str(getattr(settings, "AUTODB_IMAGE_BASE_URL", "https://order24-file.utr.ua/")).strip().rstrip("/")
    if raw_path.startswith("http://") or raw_path.startswith("https://"):
        return raw_path
    if not raw_path.startswith("/"):
        raw_path = f"/{raw_path}"
    return f"{base_url}{raw_path}"


def _normalize_article_info_text(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    first_line = raw.splitlines()[0]
    compact = " ".join(first_line.split()).strip()
    return compact[:1000]


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "t", "yes", "y"}


def _to_int(value: Any, *, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
