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
from apps.autodb.services.remote_client import AutoDbProRemoteClient, AutoDbProRemoteClientError
from apps.autodb.services.column_helpers import find_column_name, find_value
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
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
    direct_supplier_id = int(getattr(product, "autodb_supplier_id", 0) or 0)
    if direct_supplier_id > 0:
        supplier_ids.add(direct_supplier_id)
    if not supplier_ids:
        return AutoDbProductContent(image_urls=[], attributes=[], product_groups=[])

    articles = {article for article, _brand in pairs}

    if prefer_live and bool(getattr(settings, "AUTODB_LIVE_CONTENT_ENABLED", True)):
        try:
            _refresh_cache_from_live(supplier_ids=supplier_ids, articles=articles)
        except Exception as exc:  # noqa: BLE001
            logger.warning("autodb_live_content_refresh_failed product_id=%s error=%s", product.id, exc)

    content = _build_content_from_cache(supplier_ids=supplier_ids, articles=articles)
    if not content.attributes or not content.product_groups:
        fallback = _build_content_from_local_clone(supplier_ids=supplier_ids, articles=articles)
        content = AutoDbProductContent(
            image_urls=content.image_urls or fallback.image_urls,
            attributes=content.attributes or fallback.attributes,
            product_groups=content.product_groups or fallback.product_groups,
        )
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
    pairs = _resolve_article_brand_pairs(product=product)
    if not pairs:
        return []
    supplier_ids = _resolve_supplier_ids(pairs=pairs)
    direct_supplier_id = int(getattr(product, "autodb_supplier_id", 0) or 0)
    if direct_supplier_id > 0:
        supplier_ids.add(direct_supplier_id)
    if not supplier_ids:
        return []
    articles = {article for article, _brand in pairs}
    content = _build_content_from_local_clone(supplier_ids=supplier_ids, articles=articles)
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
            name = _load_article_name_from_remote_gateway(
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


def _build_content_from_local_clone(*, supplier_ids: set[int], articles: set[str]) -> AutoDbProductContent:
    try:
        storage = AutoDbRawCloneStorage()
    except Exception:  # noqa: BLE001
        return AutoDbProductContent(image_urls=[], attributes=[], product_groups=[])

    attributes = _build_attributes_from_local_clone(storage=storage, supplier_ids=supplier_ids, articles=articles)
    product_groups = _build_groups_from_local_clone(storage=storage, supplier_ids=supplier_ids, articles=articles)
    return AutoDbProductContent(
        image_urls=[],
        attributes=attributes,
        product_groups=product_groups,
    )


def _build_attributes_from_local_clone(
    *,
    storage: AutoDbRawCloneStorage,
    supplier_ids: set[int],
    articles: set[str],
) -> list[dict[str, str]]:
    try:
        storage.ensure_table("article_attributes")
        columns = list(storage.get_local_columns("article_attributes"))
    except Exception:  # noqa: BLE001
        return []

    supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
    article_col = find_column_name(
        columns,
        ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articleNumber", "articlenumber", "article", "number"],
    )
    description_col = find_column_name(columns, ["description", "Description"])
    name_col = find_column_name(columns, ["attributeName", "name", "title", "criterionName", "criteriaName", "displaytitle"])
    value_col = find_column_name(columns, ["attributeValue", "value", "criterionValue", "criteriaValue", "displayvalue", "description"])
    unit_col = find_column_name(columns, ["unit", "measureUnit", "uom"])
    if not supplier_col or not article_col:
        return []

    rows = _fetch_clone_rows(
        storage=storage,
        table="article_attributes",
        supplier_col=supplier_col,
        article_col=article_col,
        supplier_ids=supplier_ids,
        articles=articles,
        columns=columns,
    )
    out: list[dict[str, str]] = []
    for row in rows:
        name_candidates = [item for item in (description_col, name_col) if item]
        clean_name = str(find_value(row, name_candidates) or "").strip()
        clean_value = str(find_value(row, [value_col]) or "").strip() if value_col else ""
        clean_unit = str(find_value(row, [unit_col]) or "").strip() if unit_col else ""
        if not clean_name or not clean_value:
            continue
        if clean_unit:
            clean_value = f"{clean_value} {clean_unit}".strip()
        out.append({"attribute_name": clean_name[:255], "value": clean_value[:255]})
        if len(out) >= 120:
            break
    return out


def _build_groups_from_local_clone(
    *,
    storage: AutoDbRawCloneStorage,
    supplier_ids: set[int],
    articles: set[str],
) -> list[dict[str, str | int]]:
    try:
        storage.ensure_table("article_prd")
        article_prd_columns = list(storage.get_local_columns("article_prd"))
    except Exception:  # noqa: BLE001
        return []

    supplier_col = find_column_name(article_prd_columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
    article_col = find_column_name(
        article_prd_columns,
        ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articleNumber", "articlenumber", "article", "number"],
    )
    prd_id_col = find_column_name(article_prd_columns, ["prdId", "productId", "productid", "groupId", "id"])
    if not supplier_col or not article_col or not prd_id_col:
        return []

    link_rows = _fetch_clone_rows(
        storage=storage,
        table="article_prd",
        supplier_col=supplier_col,
        article_col=article_col,
        supplier_ids=supplier_ids,
        articles=articles,
        columns=article_prd_columns,
    )
    group_ids: list[int] = []
    seen_ids: set[int] = set()
    for row in link_rows:
        raw_id = find_value(row, [prd_id_col])
        group_id = _to_int(raw_id)
        if not group_id or group_id in seen_ids:
            continue
        seen_ids.add(group_id)
        group_ids.append(group_id)
        if len(group_ids) >= 120:
            break
    if not group_ids:
        return []

    names_by_id: dict[int, str] = {}
    try:
        storage.ensure_table("prd")
        prd_columns = list(storage.get_local_columns("prd"))
        id_col = find_column_name(prd_columns, ["id", "prdId", "productId", "productid"])
        name_col = find_column_name(prd_columns, ["description", "name", "title", "text", "fullDescription"])
        if id_col and name_col:
            prd_rows = storage.fetch_local_rows_in(
                table="prd",
                column=id_col,
                values=group_ids,
                limit=max(len(group_ids) * 3, 200),
                columns=prd_columns,
            )
            for row in prd_rows:
                parsed_id = _to_int(find_value(row, [id_col]))
                if not parsed_id:
                    continue
                names_by_id[parsed_id] = str(find_value(row, [name_col]) or "").strip()[:255]
    except Exception:  # noqa: BLE001
        names_by_id = {}

    out: list[dict[str, str | int]] = []
    for group_id in group_ids:
        out.append(
            {
                "prd_id": group_id,
                "prd_name": names_by_id.get(group_id, ""),
            }
        )
    return out


def _fetch_clone_rows(
    *,
    storage: AutoDbRawCloneStorage,
    table: str,
    supplier_col: str,
    article_col: str,
    supplier_ids: set[int],
    articles: set[str],
    columns: list[str],
) -> list[dict[str, Any]]:
    if not supplier_ids or not articles:
        return []
    rows: list[dict[str, Any]] = []
    for supplier_id in sorted(supplier_ids):
        try:
            chunk = storage.fetch_local_rows_in(
                table=table,
                column=article_col,
                values=sorted(articles),
                extra_filters={supplier_col: supplier_id},
                limit=3000,
                columns=columns,
            )
        except Exception:  # noqa: BLE001
            continue
        if chunk:
            rows.extend(chunk)
    return rows


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
        best = _pick_best_article_name(rows)
        if best:
            return best

        sql_prd = (
            "SELECT p.description, p.normalizeddescription "
            "FROM article_prd ap "
            "LEFT JOIN prd p ON p.id = ap.productId "
            f"WHERE ap.supplierid IN ({supplier_placeholders}) "
            f"AND ap.datasupplierarticlenumber IN ({article_placeholders})"
        )
        cursor = source.cursor()
        try:
            cursor.execute(sql_prd, params)
            prd_rows = cursor.fetchall()
        finally:
            cursor.close()
        return _pick_best_prd_fallback_name(prd_rows)
    finally:
        source.close()


def _load_article_name_from_remote_gateway(*, article_candidates: set[str], normalized_brand: str) -> str:
    if not article_candidates or not normalized_brand:
        return ""
    try:
        client = AutoDbProRemoteClient.from_settings()
    except AutoDbProRemoteClientError:
        return ""

    supplier_ids = _fetch_supplier_ids_from_remote_gateway(client=client, normalized_brand=normalized_brand)
    if not supplier_ids:
        return ""

    supplier_placeholders = ", ".join(["%s"] * len(supplier_ids))
    article_placeholders = ", ".join(["%s"] * len(article_candidates))
    sql = (
        "SELECT InformationType AS info_type, InformationText AS info_text "
        "FROM article_inf "
        f"WHERE supplierId IN ({supplier_placeholders}) "
        f"AND DataSupplierArticleNumber IN ({article_placeholders})"
    )
    params = (*sorted(supplier_ids), *sorted(article_candidates))
    rows = client.select(sql, tuple(params), run_id="catalog-article-name")
    normalized_rows = [
        (item.get("info_type"), item.get("info_text"))
        for item in rows
        if isinstance(item, dict)
    ]
    best = _pick_best_article_name(normalized_rows)
    if best:
        return best

    sql_prd = (
        "SELECT p.description AS prd_description, p.normalizeddescription AS prd_normalized "
        "FROM article_prd ap "
        "LEFT JOIN prd p ON p.id = ap.productId "
        f"WHERE ap.supplierid IN ({supplier_placeholders}) "
        f"AND ap.datasupplierarticlenumber IN ({article_placeholders})"
    )
    prd_rows = client.select(sql_prd, tuple(params), run_id="catalog-article-name-prd-fallback")
    normalized_prd_rows = [
        (item.get("prd_description"), item.get("prd_normalized"))
        for item in prd_rows
        if isinstance(item, dict)
    ]
    return _pick_best_prd_fallback_name(normalized_prd_rows)


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
    name_col = _pick_column(columns, ("attributeName", "name", "title", "criterionName", "criteriaName", "displaytitle"))
    value_col = _pick_column(columns, ("attributeValue", "value", "criterionValue", "criteriaValue", "displayvalue", "description"))
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


def _pick_best_prd_fallback_name(rows: list[tuple[Any, ...]]) -> str:
    for description, normalized in rows:
        for candidate in (description, normalized):
            clean = _normalize_article_info_text(candidate)
            if clean:
                return clean[:255]
    return ""


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


def _fetch_supplier_ids_from_remote_gateway(*, client: AutoDbProRemoteClient, normalized_brand: str) -> set[int]:
    if not normalized_brand:
        return set()
    brand_value = normalized_brand.strip().upper()
    rows = client.select(
        (
            "SELECT id FROM suppliers "
            "WHERE UPPER(TRIM(matchcode)) = %s OR UPPER(TRIM(description)) = %s"
        ),
        (brand_value, brand_value),
        run_id="catalog-supplier-ids",
    )
    supplier_ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = _to_int(row.get("id"))
        if value:
            supplier_ids.add(value)
    return supplier_ids


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
    fallback_brand = normalize_brand(
        str(getattr(product, "display_brand_name", "") or "").strip()
        or str(getattr(product, "autodb_supplier_name", "") or "").strip()
        or str(getattr(product, "normalized_brand", "") or "").strip()
    )

    def _add_article_candidates(*, raw_article: str, normalized_article: str, brand: str) -> None:
        if not brand:
            return
        for candidate in _build_article_candidates(article_raw=raw_article, normalized_article=normalized_article):
            clean_candidate = str(candidate or "").strip()
            if clean_candidate:
                pairs.add((clean_candidate, brand))

    product_article_raw = str(getattr(product, "article", "") or "").strip()
    product_article_normalized = normalize_article(product_article_raw)
    if fallback_brand:
        _add_article_candidates(
            raw_article=product_article_raw,
            normalized_article=product_article_normalized,
            brand=fallback_brand,
        )
        autodb_article_raw = str(getattr(product, "autodb_article_number", "") or "").strip()
        _add_article_candidates(
            raw_article=autodb_article_raw,
            normalized_article=normalize_article(autodb_article_raw),
            brand=fallback_brand,
        )

    raw_offers = (
        SupplierRawOffer.objects.filter(matched_product_id=product.id)
        .values_list("article", "normalized_article", "brand_name", "normalized_brand")
        .distinct()
    )
    for raw_article, normalized_article, raw_brand, normalized_brand in raw_offers:
        clean_brand = str(normalized_brand or "").strip() or normalize_brand(str(raw_brand or "").strip()) or fallback_brand
        if not clean_brand:
            continue
        _add_article_candidates(
            raw_article=str(raw_article or ""),
            normalized_article=str(normalized_article or ""),
            brand=clean_brand,
        )
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

    base_url = str(getattr(settings, "AUTODB_IMAGE_BASE_URL", "https://image.auto-db.pro/images/")).strip().rstrip("/")
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
