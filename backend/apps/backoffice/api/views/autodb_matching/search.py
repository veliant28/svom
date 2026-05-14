from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from django.conf import settings
from django.db import DatabaseError, connections, transaction

from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.column_helpers import find_column_name
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage

from .utils import safe_str, supplier_display_name

ARTICLE_TABLES = ("article_numbers", "articles")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
HTTP_URL_RE = re.compile(r"https?://[^\\s'\"<>]+", re.IGNORECASE)


class ManualAutoDbSearch:
    def __init__(
        self,
        *,
        storage: AutoDbRawCloneStorage | None = None,
        normalizer: ArticleNumberNormalizer | None = None,
    ):
        self.storage = storage or AutoDbRawCloneStorage()
        self.normalizer = normalizer or ArticleNumberNormalizer()

    def variants(self, article: str) -> list[str]:
        normalized = self.normalizer.normalize(article)
        values = [normalized.original, normalized.original.upper(), normalized.canonical, normalized.normalized]
        values.extend(normalized.search_variants)
        out: list[str] = []
        for item in values:
            value = safe_str(item).upper()
            if value and value not in out:
                out.append(value)
        return out

    def local(self, *, supplier_id: int, supplier_name: str, article: str) -> dict[str, Any]:
        self._ensure_connection_ready()
        raw_article = safe_str(article)
        normalized = self.normalizer.normalize(raw_article)
        variants = self.variants(raw_article)
        matched_table = ""
        matched_article = ""
        matched_row: dict[str, Any] = {}
        local_hits = 0

        for table in ARTICLE_TABLES:
            columns = self.storage.get_local_columns(table)
            supplier_col, article_col = self._supplier_article_columns(columns)
            if not supplier_col or not article_col:
                continue
            for variant in variants[:8]:
                rows = self._safe_fetch_local_rows(
                    table=table,
                    filters={supplier_col: supplier_id, article_col: variant},
                    columns=self._selected_columns(columns),
                    limit=5,
                )
                if not rows:
                    continue
                local_hits += len(rows)
                if not matched_table:
                    matched_table = table
                    matched_row = rows[0]
                    matched_article = safe_str(rows[0].get(article_col) or variant)
                break
            if matched_table:
                break

        article_for_linkage = matched_article or normalized.normalized or normalized.canonical
        article_prd_rows, article_links_rows, prd_rows, prd_ids = self._linkage_counts(
            supplier_id=supplier_id,
            article_number=article_for_linkage,
        )
        attributes_rows = self._count_rows(table="article_attributes", supplier_id=supplier_id, article_number=article_for_linkage)
        fitment_rows = self._count_rows(table="article_li", supplier_id=supplier_id, article_number=article_for_linkage)
        image_rows = self._count_rows(table="article_images", supplier_id=supplier_id, article_number=article_for_linkage)
        previews = self._build_previews(
            supplier_id=supplier_id,
            article_number=article_for_linkage,
            source="local",
        )
        linkage_present = (article_prd_rows + article_links_rows) > 0 and prd_rows > 0
        status_value = "not_found"
        if matched_table and linkage_present:
            status_value = "exact_local_found"
        elif matched_table:
            status_value = "no_prd_linkage"
        details_article = previews["article"] if previews["article"] else matched_row
        if matched_row:
            details_article = {**details_article, **matched_row}

        return {
            "source": "local",
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "supplier_description": supplier_name,
            "supplier_matchcode": "",
            "article_input": raw_article,
            "variants": variants,
            "searched_article": raw_article,
            "matched_stored_article": matched_article,
            "article_id": self._article_id(matched_row),
            "article_key": f"{supplier_id}:{matched_article}" if matched_article else "",
            "prd_linkage_present": linkage_present,
            "prd_id": prd_ids[0] if prd_ids else None,
            "generic": "",
            "category_metadata_present": prd_rows > 0,
            "attributes_available_count": attributes_rows,
            "fitments_available_count": fitment_rows,
            "images_available_count": image_rows,
            "image_thumbnails": previews["image_thumbnails"],
            "status": status_value,
            "matched_table": matched_table,
            "source_path": "auto_db_pro local clone: article_numbers/articles exact variants",
            "confidence": "deterministic_exact",
            "reason": "local deterministic exact variants only; fuzzy/OE/cross/name disabled",
            "counts": {
                "local_hits": local_hits,
                "article_prd_rows": article_prd_rows,
                "article_links_rows": article_links_rows,
                "prd_rows": prd_rows,
            },
            "details": {
                "article": details_article,
                "prd_ids": prd_ids[:20],
                "attributes_preview": previews["attributes_preview"],
                "compatibility_preview": previews["compatibility_preview"],
            },
        }

    def local_candidates(self, *, article: str, limit: int = 80) -> list[dict[str, Any]]:
        self._ensure_connection_ready()
        variants = self.variants(article)
        candidates: dict[tuple[int, str], dict[str, Any]] = {}
        for table in ARTICLE_TABLES:
            columns = self.storage.get_local_columns(table)
            supplier_col, article_col = self._supplier_article_columns(columns)
            if not supplier_col or not article_col:
                continue
            for variant in variants[:8]:
                rows = self._safe_fetch_local_rows(
                    table=table,
                    filters={article_col: variant},
                    columns=[supplier_col, article_col],
                    limit=500,
                )
                for row in rows:
                    supplier_id = self._safe_int(row.get(supplier_col))
                    article_value = safe_str(row.get(article_col) or variant).upper()
                    if supplier_id is None or not article_value:
                        continue
                    key = (supplier_id, article_value)
                    if key not in candidates:
                        candidates[key] = {
                            "supplier_id": supplier_id,
                            "supplier_name": supplier_display_name(supplier_id),
                            "matched_stored_article": article_value,
                            "hits": 0,
                            "matched_table": table,
                        }
                    candidates[key]["hits"] = int(candidates[key]["hits"]) + 1
        ordered = sorted(
            candidates.values(),
            key=lambda item: (-int(item["hits"]), safe_str(item["supplier_name"]), int(item["supplier_id"])),
        )
        return ordered[: max(int(limit), 1)]

    def _supplier_article_columns(self, columns: set[str] | list[str]) -> tuple[str | None, str | None]:
        supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id", "supplier"])
        article_col = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articleNumber", "articlenumber", "article", "number"],
        )
        return supplier_col, article_col

    def _selected_columns(self, columns: set[str]) -> list[str]:
        lower = {col.lower() for col in columns}
        preferred = [
            "id",
            "articleId",
            "articleid",
            "ArticleId",
            "supplierId",
            "supplierid",
            "DataSupplierArticleNumber",
            "datasupplierarticlenumber",
            "articleNumber",
            "articlenumber",
            "description",
            "genericArticleId",
            "genericarticleid",
        ]
        selected = [item for item in preferred if item in columns or item.lower() in lower]
        return selected or list(sorted(columns))[:12]

    def _article_id(self, row: dict[str, Any]) -> str:
        for key in ("id", "articleId", "articleid", "ArticleId"):
            if row.get(key) not in (None, ""):
                return safe_str(row.get(key))
        return ""

    def _linkage_counts(self, *, supplier_id: int, article_number: str) -> tuple[int, int, int, list[int]]:
        product_ids: list[int] = []
        article_prd_rows = self._linkage_table_rows(
            table="article_prd",
            supplier_id=supplier_id,
            article_number=article_number,
            product_ids=product_ids,
        )
        article_links_rows = self._linkage_table_rows(
            table="article_links",
            supplier_id=supplier_id,
            article_number=article_number,
            product_ids=product_ids,
        )
        unique_ids = sorted({item for item in product_ids if item > 0})
        if not unique_ids:
            return article_prd_rows, article_links_rows, 0, []

        prd_columns = self.storage.get_local_columns("prd")
        prd_id_col = find_column_name(prd_columns, ["id", "productId", "productid", "ProductId", "prdId", "prdid"])
        if not prd_id_col:
            return article_prd_rows, article_links_rows, 0, unique_ids
        prd_rows = self._safe_fetch_local_rows_in(
            table="prd",
            column=prd_id_col,
            values=unique_ids,
            columns=[prd_id_col],
            limit=max(len(unique_ids) * 2, 100),
        )
        return article_prd_rows, article_links_rows, len(prd_rows), unique_ids

    def _linkage_table_rows(self, *, table: str, supplier_id: int, article_number: str, product_ids: list[int]) -> int:
        columns = self.storage.get_local_columns(table)
        supplier_col, article_col = self._supplier_article_columns(columns)
        product_col = find_column_name(columns, ["productId", "productid", "ProductId", "prdId", "prdid", "id"])
        if not supplier_col or not article_col or not product_col:
            return 0
        rows = self._safe_fetch_local_rows(
            table=table,
            filters={supplier_col: supplier_id, article_col: article_number},
            columns=[product_col],
            limit=5000,
        )
        for row in rows:
            try:
                product_ids.append(int(row.get(product_col)))
            except (TypeError, ValueError):
                continue
        return len(rows)

    def _count_rows(self, *, table: str, supplier_id: int, article_number: str) -> int:
        columns = self.storage.get_local_columns(table)
        supplier_col, article_col = self._supplier_article_columns(columns)
        if not supplier_col or not article_col:
            return 0
        rows = self._safe_fetch_local_rows(
            table=table,
            filters={supplier_col: supplier_id, article_col: article_number},
            columns=[article_col],
            limit=5000,
        )
        return len(rows)

    def build_remote_previews(self, *, supplier_id: int, article_number: str) -> dict[str, Any]:
        return self._build_previews(supplier_id=supplier_id, article_number=article_number, source="remote")

    def _safe_fetch_local_rows(self, **kwargs) -> list[dict[str, Any]]:
        try:
            with transaction.atomic(using=self.storage.db_alias):
                return self.storage.fetch_local_rows(**kwargs)
        except DatabaseError:
            return []

    def _safe_fetch_local_rows_in(self, **kwargs) -> list[dict[str, Any]]:
        try:
            with transaction.atomic(using=self.storage.db_alias):
                return self.storage.fetch_local_rows_in(**kwargs)
        except DatabaseError:
            return []

    def _ensure_connection_ready(self) -> None:
        connection = connections[self.storage.db_alias]
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            try:
                connection.rollback()
            except DatabaseError:
                pass

    def _safe_int(self, value: Any) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _build_previews(self, *, supplier_id: int, article_number: str, source: str) -> dict[str, Any]:
        attributes_limit = 80 if source != "remote" else 30
        images_limit = 40 if source != "remote" else 12
        article_row = self._article_row(supplier_id=supplier_id, article_number=article_number, source=source)
        attribute_rows = self._article_rows(
            table="article_attributes",
            supplier_id=supplier_id,
            article_number=article_number,
            source=source,
            limit=attributes_limit,
        )
        image_rows = self._article_rows(
            table="article_images",
            supplier_id=supplier_id,
            article_number=article_number,
            source=source,
            limit=images_limit,
        )
        return {
            "article": article_row,
            "attributes_preview": self._attribute_preview(attribute_rows),
            "compatibility_preview": self._compatibility_preview(
                supplier_id=supplier_id,
                article_number=article_number,
                source=source,
            ),
            "image_thumbnails": self._extract_image_urls(image_rows),
        }

    def _article_row(self, *, supplier_id: int, article_number: str, source: str) -> dict[str, Any]:
        rows = self._article_rows(
            table="articles",
            supplier_id=supplier_id,
            article_number=article_number,
            source=source,
            limit=1,
        )
        return rows[0] if rows else {}

    def _article_rows(self, *, table: str, supplier_id: int, article_number: str, source: str, limit: int) -> list[dict[str, Any]]:
        if source == "remote":
            return self._fetch_remote_rows(table=table, supplier_id=supplier_id, article_number=article_number, limit=limit)
        return self._fetch_local_rows(table=table, supplier_id=supplier_id, article_number=article_number, limit=limit)

    def _fetch_local_rows(self, *, table: str, supplier_id: int, article_number: str, limit: int) -> list[dict[str, Any]]:
        columns = self.storage.get_local_columns(table)
        supplier_col, article_col = self._supplier_article_columns(columns)
        if not supplier_col or not article_col:
            return []
        selected = list(sorted(columns))[:40]
        return self._safe_fetch_local_rows(
            table=table,
            filters={supplier_col: supplier_id, article_col: article_number},
            columns=selected,
            limit=limit,
        )

    def _fetch_remote_rows(self, *, table: str, supplier_id: int, article_number: str, limit: int) -> list[dict[str, Any]]:
        try:
            columns = self.storage.get_remote_columns(table)
            supplier_col, article_col = self._supplier_article_columns(columns)
            if not supplier_col or not article_col:
                return []
            selected = list(columns)[:40]
            return self.storage.fetch_remote_rows_exact(
                table=table,
                filters={supplier_col: supplier_id, article_col: article_number},
                columns=selected,
                limit=limit,
            )
        except Exception:  # noqa: BLE001
            return []

    def _attribute_preview(self, rows: list[dict[str, Any]]) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            name = safe_str(
                row.get("description")
                or row.get("Description")
                or row.get("displaytitle")
                or row.get("DisplayTitle")
                or row.get("attributeName")
                or row.get("attributename")
            )
            value = safe_str(
                row.get("displayvalue")
                or row.get("DisplayValue")
                or row.get("value")
                or row.get("Value")
                or row.get("description")
            )
            if not name and not value:
                continue
            key = (name.casefold(), value.casefold())
            if key in seen:
                continue
            seen.add(key)
            out.append({"name": name or "-", "value": value or "-"})
        return out[:30]

    def _compatibility_preview(self, *, supplier_id: int, article_number: str, source: str) -> list[dict[str, Any]]:
        linkage_limit = 250 if source != "remote" else 80
        linkage_rows = self._article_rows(
            table="article_li",
            supplier_id=supplier_id,
            article_number=article_number,
            source=source,
            limit=linkage_limit,
        )
        linkage_meta: list[tuple[int, str]] = []
        for row in linkage_rows:
            linkage = self._safe_int(row.get("linkageId") or row.get("linkageid"))
            if linkage is not None:
                linkage_type = safe_str(row.get("linkageTypeId") or row.get("linkagetypeid")) or "PassengerCar"
                linkage_meta.append((linkage, linkage_type))
        linkage_meta = list(dict.fromkeys(linkage_meta))[:60]
        if not linkage_meta:
            return []
        passenger_linkage_ids = [linkage_id for linkage_id, linkage_type in linkage_meta if linkage_type.casefold() == "passengercar"]
        cars = self._passenger_cars_by_ids(linkage_ids=passenger_linkage_ids, source=source)
        model_ids = [self._safe_int(item.get("modelid") or item.get("modelId")) for item in cars.values()]
        model_ids = [item for item in model_ids if item is not None]
        models = self._models_by_ids(model_ids=model_ids[:120], source=source)
        out: list[dict[str, Any]] = []
        for linkage_id, linkage_type in linkage_meta:
            car = cars.get(linkage_id, {})
            model_id = self._safe_int(car.get("modelid") or car.get("modelId"))
            model = models.get(model_id or -1, {})
            model_desc = safe_str(model.get("description"))
            model_full = safe_str(model.get("fulldescription"))
            make = safe_str(model_full.replace(model_desc, "").strip()) if model_desc and model_full.endswith(model_desc) else ""
            if not make and model_full:
                parts = model_full.split(" ", 1)
                make = parts[0]
            label = safe_str(car.get("fulldescription") or model_full)
            if not label:
                label = f"{linkage_type} #{linkage_id}"
            out.append(
                {
                    "id": linkage_id,
                    "make": make,
                    "model": model_desc or linkage_type,
                    "label": label,
                    "modification": safe_str(car.get("description")),
                    "engine": "",
                    "generation": safe_str(car.get("constructioninterval")),
                    "linkage_type": linkage_type,
                }
            )
        return out[:40]

    def _passenger_cars_by_ids(self, *, linkage_ids: list[int], source: str) -> dict[int, dict[str, Any]]:
        if not linkage_ids:
            return {}
        rows: list[dict[str, Any]] = []
        if source == "remote":
            try:
                rows = self.storage.fetch_remote_rows_in(
                    table="passanger_cars",
                    column="id",
                    values=linkage_ids[:60],
                    columns=["id", "modelid", "description", "fulldescription", "constructioninterval"],
                    limit=120,
                )
            except Exception:  # noqa: BLE001
                rows = []
        else:
            rows = self._safe_fetch_local_rows_in(
                table="passanger_cars",
                column="id",
                values=linkage_ids[:60],
                columns=["id", "modelid", "description", "fulldescription", "constructioninterval"],
                limit=120,
            )
        out: dict[int, dict[str, Any]] = {}
        for row in rows:
            linkage = self._safe_int(row.get("id"))
            if linkage is not None and linkage not in out:
                out[linkage] = row
        return out

    def _models_by_ids(self, *, model_ids: list[int], source: str) -> dict[int, dict[str, Any]]:
        if not model_ids:
            return {}
        rows: list[dict[str, Any]] = []
        unique_ids = list(dict.fromkeys(model_ids))[:120]
        if source == "remote":
            try:
                rows = self.storage.fetch_remote_rows_in(
                    table="models",
                    column="id",
                    values=unique_ids,
                    columns=["id", "description", "fulldescription"],
                    limit=160,
                )
            except Exception:  # noqa: BLE001
                rows = []
        else:
            rows = self._safe_fetch_local_rows_in(
                table="models",
                column="id",
                values=unique_ids,
                columns=["id", "description", "fulldescription"],
                limit=160,
            )
        out: dict[int, dict[str, Any]] = {}
        for row in rows:
            model_id = self._safe_int(row.get("id"))
            if model_id is not None and model_id not in out:
                out[model_id] = row
        return out

    def _fetch_remote_rows_by_id(self, *, table: str, id_column: str, item_id: int, columns: list[str]) -> list[dict[str, Any]]:
        try:
            remote_columns = self.storage.get_remote_columns(table)
            by_lower = {str(col).lower(): str(col) for col in remote_columns}
            resolved_id = by_lower.get(id_column.lower())
            if not resolved_id:
                return []
            selected = [by_lower.get(col.lower()) for col in columns]
            selected_clean = [col for col in selected if col]
            return self.storage.fetch_remote_rows_exact(
                table=table,
                filters={resolved_id: item_id},
                columns=selected_clean or None,
                limit=1,
            )
        except Exception:  # noqa: BLE001
            return []

    def _extract_image_urls(self, rows: list[dict[str, Any]]) -> list[str]:
        out: list[str] = []
        for row in rows:
            for key in ("TecdocHyperlinkName", "tecdochyperlinkname", "url", "Url", "URL", "FileName", "PictureName", "DocumentName"):
                value = safe_str(row.get(key))
                url = self._normalize_image_url(value)
                if url and url not in out:
                    out.append(url)
            if len(out) >= 12:
                break
        return out[:12]

    def _normalize_image_url(self, value: str) -> str:
        if not value:
            return ""
        matched = HTTP_URL_RE.search(value)
        if matched:
            return matched.group(0)
        if value.startswith("//"):
            return f"https:{value}"

        path = urlsplit(value).path.lower()
        if not any(path.endswith(ext) for ext in IMAGE_EXTENSIONS):
            return ""

        if value.startswith(("http://", "https://")):
            return value

        base_url = str(getattr(settings, "AUTODB_PRO_IMAGE_BASE_URL", "") or "").strip().rstrip("/")
        if not base_url:
            base_url = str(getattr(settings, "AUTODB_IMAGE_BASE_URL", "") or "").strip().rstrip("/")
        if not base_url:
            return ""

        raw_path = value if value.startswith("/") else f"/{value}"
        return f"{base_url}{raw_path}"


def remote_result_payload(
    result,
    *,
    article: str,
    variants: list[str],
    previews: dict[str, Any] | None = None,
) -> dict[str, Any]:
    matched_article = safe_str(getattr(result, "remote_stored_article", ""))
    status_value = "exact_remote_found" if bool(getattr(result, "found", False)) else "not_found"
    if bool(getattr(result, "found", False)) and not bool(getattr(result, "linkage_present", False)):
        status_value = "no_prd_linkage"
    preview_payload = previews if isinstance(previews, dict) else {}
    attributes_preview = preview_payload.get("attributes_preview") if isinstance(preview_payload.get("attributes_preview"), list) else []
    compatibility_preview = preview_payload.get("compatibility_preview") if isinstance(preview_payload.get("compatibility_preview"), list) else []
    image_thumbnails = preview_payload.get("image_thumbnails") if isinstance(preview_payload.get("image_thumbnails"), list) else []
    article_details = preview_payload.get("article") if isinstance(preview_payload.get("article"), dict) else {}
    return {
        "source": safe_str(getattr(result, "matched_source", "")) or "remote",
        "supplier_id": getattr(result, "supplier_id", None),
        "supplier_name": safe_str(getattr(result, "supplier_name", "")),
        "supplier_description": safe_str(getattr(result, "supplier_name", "")),
        "supplier_matchcode": "",
        "article_input": article,
        "variants": variants,
        "searched_article": article,
        "matched_stored_article": matched_article,
        "article_id": "",
        "article_key": f"{getattr(result, 'supplier_id', '')}:{matched_article}" if matched_article else "",
        "prd_linkage_present": bool(getattr(result, "linkage_present", False)),
        "prd_id": None,
        "generic": "",
        "category_metadata_present": int(getattr(result, "prd_rows", 0) or 0) > 0,
        "attributes_available_count": len(attributes_preview),
        "fitments_available_count": len(compatibility_preview),
        "images_available_count": len(image_thumbnails),
        "image_thumbnails": image_thumbnails,
        "status": status_value,
        "matched_table": safe_str(getattr(result, "matched_table", "")),
        "source_path": safe_str(getattr(result, "path", "")),
        "endpoint": safe_str(getattr(result, "endpoint", "")),
        "confidence": "deterministic_exact",
        "reason": "remote deterministic exact variants only; fuzzy/OE/cross/name disabled",
        "counts": {
            "local_hits": int(getattr(result, "local_hits", 0) or 0),
            "remote_hits": int(getattr(result, "remote_hits", 0) or 0),
            "remote_queries": int(getattr(result, "remote_queries", 0) or 0),
            "article_prd_rows": int(getattr(result, "article_prd_rows", 0) or 0),
            "article_links_rows": int(getattr(result, "article_links_rows", 0) or 0),
            "prd_rows": int(getattr(result, "prd_rows", 0) or 0),
        },
        "details": {
            "article": article_details,
            "prd_ids": [],
            "attributes_preview": attributes_preview,
            "compatibility_preview": compatibility_preview,
        },
    }
