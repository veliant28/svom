from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.column_helpers import find_column_name, find_value
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand

SUPPLIER_TABLE = "suppliers"
SUPPLIER_DETAILS_TABLE = "supplier_details"
ARTICLES_TABLE = "articles"
ARTICLE_NUMBERS_TABLE = "article_numbers"


@dataclass(frozen=True)
class ArticleLookupResult:
    found: bool
    normalized_brand: str
    normalized_article: str
    supplier_id: int | None
    article_key: str
    article_id: int | None
    canonical_article_number: str
    canonical_brand: str
    supplier_source: str
    article_source: str
    raw_local_refs: dict[str, Any] = field(default_factory=dict)
    populated_tables: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    article_search_variants: tuple[str, ...] = field(default_factory=tuple)
    remote_supplier_called: bool = False
    remote_article_called: bool = False


class AutoDbArticleLookupService:
    HIGH_CONFIDENCE_ALIAS = 0.9

    def __init__(self, *, storage: AutoDbRawCloneStorage | None = None):
        self.storage = storage or AutoDbRawCloneStorage()
        self.article_normalizer = ArticleNumberNormalizer()

    def lookup(self, *, brand_name: str, article: str, allow_remote: bool = True) -> ArticleLookupResult:
        normalized_brand = normalize_brand(brand_name)
        normalized_article = normalize_article(article)
        article_norm = self.article_normalizer.normalize(article)
        article_variants = article_norm.search_variants or tuple(item for item in [article, normalized_article] if str(item or "").strip())
        warnings: list[str] = []
        populated_tables: dict[str, int] = {}

        supplier_row, supplier_source, supplier_fill, supplier_remote_called = self._resolve_supplier(
            brand_name=brand_name,
            normalized_brand=normalized_brand,
            allow_remote=allow_remote,
        )
        populated_tables.update(supplier_fill)
        supplier_id = self._coerce_int(find_value(supplier_row or {}, ["id"]))

        article_row, article_source, article_fill, article_remote_called = self._resolve_article(
            supplier_id=supplier_id,
            article_raw=article,
            normalized_article=normalized_article,
            article_variants=article_variants,
            allow_remote=allow_remote,
        )
        populated_tables.update(article_fill)

        article_id = self._coerce_int(find_value(article_row or {}, ["articleid", "id"]))
        canonical_article_number = self._resolve_canonical_article_number(article_row)
        article_key = self._compose_article_key(supplier_id=supplier_id, article_number=canonical_article_number)
        canonical_brand = self._resolve_canonical_brand(supplier_row, normalized_brand)

        if supplier_row is None:
            warnings.append("supplier_not_found")
        if article_row is None:
            warnings.append("article_not_found")

        found = supplier_row is not None and bool(canonical_article_number)
        refs = {
            "suppliers": {"id": supplier_id} if supplier_id is not None else {},
            "article_numbers": (
                {"articleid": article_id}
                if article_id is not None
                else (
                    {"supplierid": supplier_id, "datasupplierarticlenumber": canonical_article_number}
                    if supplier_id is not None and canonical_article_number
                    else {}
                )
            ),
            "articles": (
                {"id": article_id}
                if article_id is not None
                else (
                    {"supplierid": supplier_id, "datasupplierarticlenumber": canonical_article_number}
                    if supplier_id is not None and canonical_article_number
                    else {}
                )
            ),
            "article_key": article_key,
        }

        return ArticleLookupResult(
            found=found,
            normalized_brand=normalized_brand,
            normalized_article=normalized_article,
            supplier_id=supplier_id,
            article_key=article_key,
            article_id=article_id,
            canonical_article_number=canonical_article_number,
            canonical_brand=canonical_brand,
            supplier_source=supplier_source,
            article_source=article_source,
            raw_local_refs=refs,
            populated_tables=populated_tables,
            warnings=warnings,
            article_search_variants=tuple(article_variants),
            remote_supplier_called=supplier_remote_called,
            remote_article_called=article_remote_called,
        )

    def _resolve_supplier(
        self,
        *,
        brand_name: str,
        normalized_brand: str,
        allow_remote: bool,
    ) -> tuple[dict[str, Any] | None, str, dict[str, int], bool]:
        local_row = self._find_supplier_local(brand_name=brand_name, normalized_brand=normalized_brand)
        if local_row is not None:
            return local_row, "local", {}, False
        if not allow_remote:
            return None, "no_remote", {}, False

        remote_rows = self._find_supplier_remote(brand_name=brand_name, normalized_brand=normalized_brand)
        if not remote_rows:
            return None, "not_found", {}, True

        failed = self.storage.upsert_rows(table=SUPPLIER_TABLE, rows=remote_rows)
        inserted = max(len(remote_rows) - failed, 0)
        populated = {SUPPLIER_TABLE: inserted}

        supplier_id = self._coerce_int(find_value(remote_rows[0], ["id"]))
        if supplier_id is not None:
            details_rows = self._find_supplier_details_remote(supplier_id)
            if details_rows:
                details_failed = self.storage.upsert_rows(table=SUPPLIER_DETAILS_TABLE, rows=details_rows)
                populated[SUPPLIER_DETAILS_TABLE] = max(len(details_rows) - details_failed, 0)

        local_row = self._find_supplier_local(brand_name=brand_name, normalized_brand=normalized_brand)
        if local_row is None:
            local_row = self._pick_supplier_row(
                rows=remote_rows,
                brand_name=brand_name,
                normalized_brand=normalized_brand,
            )
        if local_row is None:
            return None, "not_found", populated, True
        return local_row, "remote", populated, True

    def _resolve_article(
        self,
        *,
        supplier_id: int | None,
        article_raw: str,
        normalized_article: str,
        article_variants: tuple[str, ...],
        allow_remote: bool,
    ) -> tuple[dict[str, Any] | None, str, dict[str, int], bool]:
        local_row = self._find_article_local(
            supplier_id=supplier_id,
            article_raw=article_raw,
            normalized_article=normalized_article,
            article_variants=article_variants,
        )
        if local_row is not None:
            return local_row, "local", {}, False
        if not allow_remote:
            return None, "no_remote", {}, False

        remote_rows = self._find_article_numbers_remote(
            supplier_id=supplier_id,
            article_raw=article_raw,
            normalized_article=normalized_article,
            article_variants=article_variants,
        )
        populated: dict[str, int] = {}
        if remote_rows:
            failed = self.storage.upsert_rows(table=ARTICLE_NUMBERS_TABLE, rows=remote_rows)
            populated[ARTICLE_NUMBERS_TABLE] = max(len(remote_rows) - failed, 0)

            article_ids = {
                self._coerce_int(find_value(item, ["articleid", "id"]))
                for item in remote_rows
            }
            article_ids.discard(None)
            for article_id in article_ids:
                rows = self._find_articles_remote_by_id(article_id=article_id, supplier_id=supplier_id)
                if not rows:
                    continue
                a_failed = self.storage.upsert_rows(table=ARTICLES_TABLE, rows=rows)
                populated[ARTICLES_TABLE] = populated.get(ARTICLES_TABLE, 0) + max(len(rows) - a_failed, 0)
        else:
            rows = self._find_articles_remote(
                supplier_id=supplier_id,
                article_raw=article_raw,
                normalized_article=normalized_article,
                article_variants=article_variants,
            )
            if rows:
                failed = self.storage.upsert_rows(table=ARTICLES_TABLE, rows=rows)
                populated[ARTICLES_TABLE] = max(len(rows) - failed, 0)

        local_row = self._find_article_local(
            supplier_id=supplier_id,
            article_raw=article_raw,
            normalized_article=normalized_article,
            article_variants=article_variants,
        )
        if local_row is not None:
            return local_row, "remote", populated, True

        return None, "not_found", populated, True

    def _find_supplier_local(self, *, brand_name: str, normalized_brand: str) -> dict[str, Any] | None:
        alias_row = self._find_supplier_local_by_alias(normalized_brand=normalized_brand)
        if alias_row is not None:
            return alias_row
        self.storage.ensure_table(SUPPLIER_TABLE)
        local_columns = list(self.storage.get_local_columns(SUPPLIER_TABLE))
        candidates = self._resolve_existing_columns(local_columns, ["matchcode", "description", "fulldescription"])
        values = [value for value in {brand_name, normalized_brand} if str(value or "").strip()]

        rows: list[dict[str, Any]] = []
        for column in candidates:
            for value in values:
                rows.extend(self.storage.fetch_local_rows(table=SUPPLIER_TABLE, filters={column: value}, limit=100))

        if not rows:
            rows = self.storage.fetch_local_rows(table=SUPPLIER_TABLE, limit=1000)
        return self._pick_supplier_row(rows=rows, brand_name=brand_name, normalized_brand=normalized_brand)

    def _find_supplier_local_by_alias(self, *, normalized_brand: str) -> dict[str, Any] | None:
        brand_key = normalize_brand(normalized_brand)
        if not brand_key:
            return None
        try:
            alias = (
                AutoDbSupplierBrandAlias.objects.filter(
                    normalized_raw_brand=brand_key,
                    is_active=True,
                )
                .order_by("-manual_confirmed", "-confidence", "updated_at")
                .first()
            )
            if alias is None:
                return None
            if (not alias.manual_confirmed) and (float(alias.confidence or 0.0) < self.HIGH_CONFIDENCE_ALIAS):
                return None
            self.storage.ensure_table(SUPPLIER_TABLE)
            rows = self.storage.fetch_local_rows(table=SUPPLIER_TABLE, filters={"id": int(alias.autodb_supplier_id)}, limit=1)
            if rows:
                return rows[0]
        except Exception:  # noqa: BLE001
            return None
        return None

    def _find_supplier_remote(self, *, brand_name: str, normalized_brand: str) -> list[dict[str, Any]]:
        columns = self.storage.get_remote_columns(SUPPLIER_TABLE)
        candidates = self._resolve_existing_columns(columns, ["matchcode", "description", "fulldescription"])
        values = [value for value in {brand_name, normalized_brand} if str(value or "").strip()]
        matched: list[dict[str, Any]] = []
        for column in candidates:
            for value in values:
                rows = self.storage.fetch_remote_rows_exact(
                    table=SUPPLIER_TABLE,
                    filters={column: value},
                    limit=25,
                )
                matched.extend(rows)
        if matched:
            return matched

        for column in candidates:
            for value in values:
                rows = self.storage.fetch_remote_rows_like(
                    table=SUPPLIER_TABLE,
                    column=column,
                    value=value,
                    limit=50,
                )
                matched.extend(rows)
        return matched

    def _find_supplier_details_remote(self, supplier_id: int) -> list[dict[str, Any]]:
        columns = self.storage.get_remote_columns(SUPPLIER_DETAILS_TABLE)
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "supplier_id", "id"])
        if not supplier_column:
            return []
        return self.storage.fetch_remote_rows_exact(
            table=SUPPLIER_DETAILS_TABLE,
            filters={supplier_column: supplier_id},
            limit=500,
        )

    def _find_article_local(
        self,
        *,
        supplier_id: int | None,
        article_raw: str,
        normalized_article: str,
        article_variants: tuple[str, ...],
    ) -> dict[str, Any] | None:
        row = self._find_article_local_in_table(
            table=ARTICLE_NUMBERS_TABLE,
            supplier_id=supplier_id,
            article_raw=article_raw,
            normalized_article=normalized_article,
            article_variants=article_variants,
        )
        if row is not None:
            return row

        return self._find_article_local_in_table(
            table=ARTICLES_TABLE,
            supplier_id=supplier_id,
            article_raw=article_raw,
            normalized_article=normalized_article,
            article_variants=article_variants,
        )

    def _find_article_local_in_table(
        self,
        *,
        table: str,
        supplier_id: int | None,
        article_raw: str,
        normalized_article: str,
        article_variants: tuple[str, ...],
    ) -> dict[str, Any] | None:
        self.storage.ensure_table(table)
        local_columns = list(self.storage.get_local_columns(table))
        supplier_column = find_column_name(local_columns, ["supplierId", "supplierid", "supplier_id", "supplier"])
        article_column = find_column_name(
            local_columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articlenumber", "article", "number"],
        )
        if not article_column:
            return None

        variants = self._build_article_variants(article_raw=article_raw, normalized_article=normalized_article, article_variants=article_variants)
        rows: list[dict[str, Any]] = []
        for value in variants:
            filters: dict[str, Any] = {article_column: value}
            if supplier_id is not None and supplier_column:
                filters[supplier_column] = supplier_id
            rows.extend(self.storage.fetch_local_rows(table=table, filters=filters, limit=200))

        return self._pick_article_row(
            rows=rows,
            supplier_id=supplier_id,
            article_raw=article_raw,
            normalized_article=normalized_article,
            article_variants=article_variants,
        )

    def _find_article_numbers_remote(
        self,
        *,
        supplier_id: int | None,
        article_raw: str,
        normalized_article: str,
        article_variants: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        columns = self.storage.get_remote_columns(ARTICLE_NUMBERS_TABLE)
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "supplier_id", "supplier"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articlenumber", "article", "number"],
        )
        if not article_column:
            return []

        filters_base: dict[str, Any] = {}
        if supplier_id is not None and supplier_column:
            filters_base[supplier_column] = supplier_id

        matched: list[dict[str, Any]] = []
        for value in self._build_article_variants(article_raw=article_raw, normalized_article=normalized_article, article_variants=article_variants):
            if not str(value or "").strip():
                continue
            filters = dict(filters_base)
            filters[article_column] = value
            matched.extend(
                self.storage.fetch_remote_rows_exact(
                    table=ARTICLE_NUMBERS_TABLE,
                    filters=filters,
                    limit=200,
                )
            )
        return matched

    def _find_articles_remote(
        self,
        *,
        supplier_id: int | None,
        article_raw: str,
        normalized_article: str,
        article_variants: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        columns = self.storage.get_remote_columns(ARTICLES_TABLE)
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "supplier_id", "supplier"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articlenumber", "article", "number"],
        )
        if not article_column:
            return []

        filters_base: dict[str, Any] = {}
        if supplier_id is not None and supplier_column:
            filters_base[supplier_column] = supplier_id

        rows: list[dict[str, Any]] = []
        for value in self._build_article_variants(article_raw=article_raw, normalized_article=normalized_article, article_variants=article_variants):
            if not str(value or "").strip():
                continue
            filters = dict(filters_base)
            filters[article_column] = value
            rows.extend(
                self.storage.fetch_remote_rows_exact(
                    table=ARTICLES_TABLE,
                    filters=filters,
                    limit=100,
                )
            )
        return rows

    def _find_articles_remote_by_id(self, *, article_id: int, supplier_id: int | None) -> list[dict[str, Any]]:
        columns = self.storage.get_remote_columns(ARTICLES_TABLE)
        article_column = find_column_name(columns, ["id", "articleid"])
        if not article_column:
            return []
        filters: dict[str, Any] = {article_column: article_id}
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "supplier_id", "supplier"])
        if supplier_id is not None and supplier_column:
            filters[supplier_column] = supplier_id
        return self.storage.fetch_remote_rows_exact(table=ARTICLES_TABLE, filters=filters, limit=20)

    def _pick_supplier_row(self, *, rows: list[dict[str, Any]], brand_name: str, normalized_brand: str) -> dict[str, Any] | None:
        if not rows:
            return None
        brand_options = {normalize_brand(brand_name), normalize_brand(normalized_brand)}
        brand_options.discard("")
        best_row: dict[str, Any] | None = None
        best_score = -1
        for row in rows:
            score = 0
            for value in [
                find_value(row, ["matchcode"]),
                find_value(row, ["description"]),
                find_value(row, ["fulldescription"]),
            ]:
                normalized_value = normalize_brand(str(value or ""))
                if normalized_value and normalized_value in brand_options:
                    score = max(score, 100)
                elif normalized_value and any(
                    self._is_safe_brand_extension(query=option, candidate=normalized_value)
                    for option in brand_options
                ):
                    score = max(score, 85)
            if best_row is None or score > best_score:
                best_row = row
                best_score = score
        return best_row if best_score > 0 else None

    def _is_safe_brand_extension(self, *, query: str, candidate: str) -> bool:
        normalized_query = normalize_brand(query)
        normalized_candidate = normalize_brand(candidate)
        if len(normalized_query) < 3 or len(normalized_candidate) < 3:
            return False
        return normalized_candidate.startswith(normalized_query) or normalized_query.startswith(normalized_candidate)

    def _pick_article_row(
        self,
        *,
        rows: list[dict[str, Any]],
        supplier_id: int | None,
        article_raw: str,
        normalized_article: str,
        article_variants: tuple[str, ...],
    ) -> dict[str, Any] | None:
        if not rows:
            return None

        article_variant_norms = {
            normalize_article(item)
            for item in self._build_article_variants(
                article_raw=article_raw,
                normalized_article=normalized_article,
                article_variants=article_variants,
            )
        }
        article_variant_norms.discard("")
        article_variant_text = {
            str(item or "").strip().upper()
            for item in self._build_article_variants(
                article_raw=article_raw,
                normalized_article=normalized_article,
                article_variants=article_variants,
            )
            if str(item or "").strip()
        }
        best_row: dict[str, Any] | None = None
        best_score = -1

        for row in rows:
            row_supplier_id = self._coerce_int(find_value(row, ["supplierId", "supplierid", "supplier_id", "SupplierId"]))
            if supplier_id is not None and row_supplier_id is not None and row_supplier_id != supplier_id:
                continue

            score = 0
            for value in [
                find_value(row, ["datasupplierarticlenumber"]),
                find_value(row, ["DataSupplierArticleNumber"]),
                find_value(row, ["articlenumber"]),
                find_value(row, ["article"]),
                find_value(row, ["number"]),
            ]:
                raw_value = str(value or "").strip().upper()
                normalized_value = normalize_article(raw_value)
                if raw_value and raw_value in article_variant_text:
                    score = max(score, 120)
                elif normalized_value and normalized_value in article_variant_norms:
                    score = max(score, 100)

            if best_row is None or score > best_score:
                best_row = row
                best_score = score

        return best_row if best_score >= 0 else None

    def _resolve_canonical_article_number(self, row: dict[str, Any] | None) -> str:
        if not row:
            return ""
        for value in [
            find_value(row, ["datasupplierarticlenumber"]),
            find_value(row, ["DataSupplierArticleNumber"]),
            find_value(row, ["articlenumber"]),
            find_value(row, ["article"]),
            find_value(row, ["number"]),
        ]:
            candidate = str(value or "").strip()
            if candidate:
                return candidate
        return ""

    def _resolve_canonical_brand(self, row: dict[str, Any] | None, fallback: str) -> str:
        if not row:
            return fallback
        for value in [
            find_value(row, ["fulldescription"]),
            find_value(row, ["description"]),
            find_value(row, ["matchcode"]),
        ]:
            candidate = str(value or "").strip()
            if candidate:
                return candidate
        return fallback

    def _compose_article_key(self, *, supplier_id: int | None, article_number: str) -> str:
        if supplier_id is None:
            return ""
        number = re.sub(r"\s+", "", str(article_number or "").strip())
        if not number:
            return ""
        return f"{supplier_id}:{number}"

    def _resolve_existing_columns(self, columns: list[str], candidates: list[str]) -> list[str]:
        resolved: list[str] = []
        for candidate in candidates:
            found = find_column_name(columns, [candidate])
            if found:
                resolved.append(found)
        return resolved

    def _coerce_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _build_article_variants(
        self,
        *,
        article_raw: str,
        normalized_article: str,
        article_variants: tuple[str, ...],
    ) -> tuple[str, ...]:
        result: list[str] = []

        def add(value: str) -> None:
            raw_item = str(value or "").strip()
            if not raw_item:
                return
            if raw_item not in result:
                result.append(raw_item)
            upper_item = raw_item.upper()
            if upper_item not in result:
                result.append(upper_item)

        add(article_raw)
        for value in article_variants:
            add(value)
        add(normalized_article)
        return tuple(result)
