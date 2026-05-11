from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.column_helpers import find_column_name
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.remote_client import AutoDbProRemoteClientError
from apps.autodb.services.supplier_brand_matcher import SupplierBrandMatcher, SupplierBrandCandidate
from apps.supplier_imports.gpl_article_resolver import GplArticleResolver
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand

_MISS = object()


@dataclass(frozen=True)
class UnlinkedLinkCandidateRow:
    product_id: str
    raw_offer_id: str
    product_name: str
    display_brand: str
    brand_source: str
    raw_brand: str
    normalized_brand: str
    raw_code: str
    raw_category: str
    raw_article: str
    raw_name: str
    raw_description: str
    raw_group: str
    raw_article_td: str
    raw_image: str
    supplier_article_candidate: str
    manufacturer_article_candidate: str
    external_sku_candidate: str
    article_from_name_candidate: str
    article_from_description_candidate: str
    ean_candidate: str
    oe_candidate: str
    local_supplier_candidates_count: int
    remote_supplier_candidates_count: int
    exact_local_article_match: str
    exact_remote_article_match: str
    normalized_article_match: str
    variant_match: str
    article_numbers_table_match: str
    article_ean_match: str
    article_oe_match: str
    article_cross_match: str
    proposed_autodb_supplier_id: str
    proposed_autodb_supplier_name: str
    proposed_autodb_article_number: str
    proposed_autodb_article_key: str
    proposed_autodb_title: str
    confidence: float
    semantic_status: str
    recommendation: str
    reason: str


@dataclass(frozen=True)
class AuditSummary:
    total_unlinked: int
    safe_auto_link_candidates: int
    safe_article_variant_candidates: int
    brand_alias_candidates: int
    external_sku_candidates: int
    article_from_name_candidates: int
    manual_mapping_needed: int
    non_auto_or_supplier_only: int
    remote_not_found: int
    unsafe_ambiguous: int
    semantic_conflict: int


class UnlinkedLinkCandidateAuditService:
    NON_AUTO_BRANDS = {"MITKA", "CS SYSTEM", "ORGANIC PRINK", "VIRA", "K2"}
    PAINT_TOKENS = (
        "емал",
        "эмал",
        "аерозол",
        "аэрозол",
        "фарб",
        "краск",
        "лак",
        "грунт",
        "очист",
        "полир",
    )
    PART_TOKENS = (
        "амортиз",
        "фильтр",
        "фільтр",
        "аккумулятор",
        "акумулятор",
        "колод",
        "тормоз",
        "гальм",
        "шрус",
        "рычаг",
        "сайлент",
        "стойк",
        "подшип",
        "підшип",
        "генератор",
        "стартер",
    )

    EAN_KEYS = ("ean", "EAN", "barcode", "Barcode", "bar_code")
    OE_KEYS = ("oe", "oem", "oe_number", "OENbr", "oeNumber")
    CROSS_KEYS = ("cross", "cross_number", "crossNumber", "reference", "references", "analogs")
    LOCAL_SUPPLIER_POOL_LIMIT = 2
    REMOTE_SUPPLIER_POOL_LIMIT = 1

    def __init__(
        self,
        *,
        storage: AutoDbRawCloneStorage | None = None,
        brand_matcher: SupplierBrandMatcher | None = None,
        article_normalizer: ArticleNumberNormalizer | None = None,
        gpl_resolver: GplArticleResolver | None = None,
    ):
        self.storage = storage or AutoDbRawCloneStorage()
        self.brand_matcher = brand_matcher or SupplierBrandMatcher(storage=self.storage)
        self.article_normalizer = article_normalizer or ArticleNumberNormalizer()
        self.gpl_resolver = gpl_resolver or GplArticleResolver()

        self._article_numbers_columns = self._resolve_article_columns(table="article_numbers")
        self._articles_columns = self._resolve_article_columns(table="articles")
        self._suppliers_columns = self._resolve_supplier_columns(local=True)
        self._remote_suppliers_columns: dict[str, str | None] | None = None

        self._remote_supplier_cache: dict[str, list[SupplierBrandCandidate]] = {}
        self._local_article_cache: dict[tuple[int, str], object] = {}
        self._remote_article_cache: dict[tuple[int, str], object] = {}

    def audit_offer(
        self,
        *,
        product_id: str,
        raw_offer_id: str,
        product_name: str,
        display_brand: str,
        brand_source: str,
        raw_brand: str,
        raw_payload: dict[str, Any],
        raw_article: str,
        external_sku: str,
        allow_remote: bool,
        source_id: str | None,
        supplier_id: str | None,
        canonical_article: str = "",
        remote_stored_article: str = "",
        mapped_supplier_id: int | str | None = None,
        deterministic_exact_only: bool = False,
    ) -> UnlinkedLinkCandidateRow:
        normalized_brand = normalize_brand(raw_brand or display_brand)
        extracted = self._extract_payload(raw_payload)

        gpl_resolved = self.gpl_resolver.resolve(
            raw_payload=raw_payload if isinstance(raw_payload, dict) else {},
            article=raw_article,
            external_sku=external_sku,
        )

        canonical_article_value = str(canonical_article or "").strip()
        remote_stored_article_value = str(remote_stored_article or "").strip()
        supplier_article_candidate = (
            canonical_article_value
            or remote_stored_article_value
            or extracted["raw_article_td"]
            or raw_article
        )
        manufacturer_article_candidate = (
            canonical_article_value
            or remote_stored_article_value
            or gpl_resolved.manufacturer_article
            or raw_article
        )
        external_sku_candidate = extracted["raw_code"] or external_sku
        article_from_name_candidate = self._extract_article_from_text(extracted["raw_name"] or product_name)
        article_from_description_candidate = self._extract_article_from_text(extracted["raw_description"])
        ean_candidate = self._extract_multi(raw_payload, self.EAN_KEYS)
        oe_candidate = self._extract_multi(raw_payload, self.OE_KEYS)

        local_brand_result = self.brand_matcher.resolve_many(
            [normalized_brand],
            source_id=source_id,
            supplier_id=supplier_id,
        ).get(normalized_brand)
        local_suppliers = tuple(local_brand_result.candidates if local_brand_result else ())

        semantic_status = self._semantic_status(
            brand=display_brand or raw_brand,
            text=" ".join(
                item
                for item in [
                    product_name,
                    extracted["raw_name"],
                    extracted["raw_description"],
                    extracted["raw_category"],
                    extracted["raw_group"],
                ]
                if item
            ),
        )

        remote_suppliers = ()
        if allow_remote and semantic_status != "conflict":
            remote_suppliers = self._resolve_remote_supplier_candidates(raw_brand=raw_brand, normalized_brand=normalized_brand)

        candidates = self._build_article_candidates(
            deterministic_exact_only=deterministic_exact_only,
            canonical_article=canonical_article_value,
            remote_stored_article=remote_stored_article_value,
            manufacturer_article_candidate=manufacturer_article_candidate,
            supplier_article_candidate=supplier_article_candidate,
            external_sku_candidate=external_sku_candidate,
            article_from_name_candidate=article_from_name_candidate,
            article_from_description_candidate=article_from_description_candidate,
        )

        local_match: tuple[str, str, str] | None = None
        remote_match: tuple[str, str, str] | None = None
        used_candidate_source = ""
        used_candidate_value = ""

        forced_supplier_id = self._safe_int(mapped_supplier_id)
        supplier_pool = [forced_supplier_id] if forced_supplier_id is not None else []
        if not supplier_pool:
            supplier_pool = [item.supplier_id for item in local_suppliers[: self.LOCAL_SUPPLIER_POOL_LIMIT]]
        if not supplier_pool:
            supplier_pool = [item.supplier_id for item in remote_suppliers[: self.REMOTE_SUPPLIER_POOL_LIMIT]] if remote_suppliers else []

        for source_name, candidate_value in candidates:
            normalized_candidate = self._normalize_candidate(candidate_value)
            if not normalized_candidate:
                continue
            for sid in supplier_pool:
                local_hit = self._find_article_local(supplier_id=sid, article_candidate=candidate_value)
                if local_hit is not None:
                    local_match = local_hit
                    used_candidate_source = source_name
                    used_candidate_value = candidate_value
                    break
            if local_match is not None:
                break
            if allow_remote:
                for sid in supplier_pool:
                    remote_hit = self._find_article_remote(supplier_id=sid, article_candidate=candidate_value)
                    if remote_hit is not None:
                        remote_match = remote_hit
                        used_candidate_source = source_name
                        used_candidate_value = candidate_value
                        break
            if remote_match is not None:
                break

        proposed_supplier_id = ""
        proposed_supplier_name = ""
        proposed_article = ""
        proposed_article_key = ""
        proposed_title = ""

        exact_local = "no"
        exact_remote = "no"
        normalized_match = "no"
        variant_match = "no"
        table_match = "no"
        recommendation = "manual_mapping_needed"
        reason = "no_supplier_or_article_match"
        confidence = 0.0

        if semantic_status == "conflict":
            recommendation = "non_auto_or_supplier_only"
            reason = "semantic_conflict_supplier_non_part"
            confidence = 0.0
        else:
            hit = local_match or remote_match
            if hit is not None and supplier_pool:
                sid, article_number, title = hit
                proposed_supplier_id = str(sid)
                candidate_entry = next((item for item in (*local_suppliers, *remote_suppliers) if int(item.supplier_id) == int(sid)), None)
                proposed_supplier_name = str(candidate_entry.supplier_description if candidate_entry else "")
                proposed_article = article_number
                proposed_article_key = f"{sid}:{article_number}" if article_number else ""
                proposed_title = title

                local_used = local_match is not None
                exact_local = "yes" if local_used and used_candidate_value and self._normalize_candidate(used_candidate_value) == self._normalize_candidate(article_number) else "no"
                exact_remote = "yes" if (not local_used) and used_candidate_value and self._normalize_candidate(used_candidate_value) == self._normalize_candidate(article_number) else "no"
                normalized_match = "yes"
                table_match = "yes"
                if used_candidate_value and used_candidate_value != article_number:
                    variant_match = "yes"

                if semantic_status == "compatible":
                    if used_candidate_source in {
                        "canonical_article_candidate",
                        "remote_stored_article_candidate",
                        "manufacturer_article_candidate",
                        "supplier_article_candidate",
                    } and exact_local == "yes":
                        recommendation = "safe_auto_link_candidate"
                        reason = f"local_exact_{used_candidate_source}"
                        confidence = 0.98
                    elif used_candidate_source in {
                        "canonical_article_candidate",
                        "remote_stored_article_candidate",
                        "manufacturer_article_candidate",
                        "supplier_article_candidate",
                    }:
                        recommendation = "safe_article_variant_candidate"
                        reason = f"local_variant_{used_candidate_source}" if local_used else f"remote_variant_{used_candidate_source}"
                        confidence = 0.95
                    elif used_candidate_source == "external_sku_candidate":
                        recommendation = "external_sku_candidate"
                        reason = "external_sku_matched"
                        confidence = 0.88
                    elif used_candidate_source == "article_from_name_candidate":
                        recommendation = "article_from_name_candidate"
                        reason = "article_token_from_name_matched"
                        confidence = 0.86
                    elif used_candidate_source == "article_from_description_candidate":
                        recommendation = "article_from_name_candidate"
                        reason = "article_token_from_description_matched"
                        confidence = 0.84
                    else:
                        recommendation = "manual_mapping_needed"
                        reason = "candidate_matched_but_not_safe"
                        confidence = 0.6
                else:
                    recommendation = "unsafe_ambiguous"
                    reason = "semantic_unclear_with_match"
                    confidence = 0.45
            else:
                if local_suppliers and not remote_suppliers:
                    recommendation = "brand_alias_candidate"
                    reason = "local_supplier_candidate_found_article_not_matched"
                    confidence = 0.65
                elif allow_remote and remote_suppliers and not local_suppliers:
                    recommendation = "brand_alias_candidate"
                    reason = "remote_supplier_candidate_found_article_not_matched"
                    confidence = 0.6
                elif allow_remote and remote_suppliers:
                    recommendation = "remote_not_found"
                    reason = "supplier_found_article_not_found_remote"
                elif allow_remote:
                    recommendation = "remote_not_found"
                    reason = "brand_and_article_not_found_remote"
                else:
                    recommendation = "manual_mapping_needed"
                    reason = "remote_not_allowed_no_match"

        return UnlinkedLinkCandidateRow(
            product_id=product_id,
            raw_offer_id=raw_offer_id,
            product_name=product_name,
            display_brand=display_brand,
            brand_source=brand_source,
            raw_brand=raw_brand,
            normalized_brand=normalized_brand,
            raw_code=extracted["raw_code"],
            raw_category=extracted["raw_category"],
            raw_article=extracted["raw_article"],
            raw_name=extracted["raw_name"],
            raw_description=extracted["raw_description"],
            raw_group=extracted["raw_group"],
            raw_article_td=extracted["raw_article_td"],
            raw_image=extracted["raw_image"],
            supplier_article_candidate=supplier_article_candidate,
            manufacturer_article_candidate=manufacturer_article_candidate,
            external_sku_candidate=external_sku_candidate,
            article_from_name_candidate=article_from_name_candidate,
            article_from_description_candidate=article_from_description_candidate,
            ean_candidate=ean_candidate,
            oe_candidate=oe_candidate,
            local_supplier_candidates_count=len(local_suppliers),
            remote_supplier_candidates_count=len(remote_suppliers),
            exact_local_article_match=exact_local,
            exact_remote_article_match=exact_remote,
            normalized_article_match=normalized_match,
            variant_match=variant_match,
            article_numbers_table_match=table_match,
            article_ean_match="yes" if ean_candidate else "no",
            article_oe_match="yes" if oe_candidate else "no",
            article_cross_match="yes" if self._extract_multi(raw_payload, self.CROSS_KEYS) else "no",
            proposed_autodb_supplier_id=proposed_supplier_id,
            proposed_autodb_supplier_name=proposed_supplier_name,
            proposed_autodb_article_number=proposed_article,
            proposed_autodb_article_key=proposed_article_key,
            proposed_autodb_title=proposed_title,
            confidence=confidence,
            semantic_status=semantic_status,
            recommendation=recommendation,
            reason=reason,
        )

    def _extract_payload(self, payload: dict[str, Any]) -> dict[str, str]:
        data = payload if isinstance(payload, dict) else {}
        return {
            "raw_code": self._first(data, ["Код", "code", "cid"]),
            "raw_category": self._first(data, ["Категорія", "Категория", "category"]),
            "raw_article": self._first(data, ["Артикул", "article"]),
            "raw_name": self._first(data, ["Найменування", "Наименование", "name", "title"]),
            "raw_description": self._first(data, ["Опис", "Описание", "description"]),
            "raw_group": self._first(data, ["Група ТД", "Группа ТД", "group"]),
            "raw_article_td": self._first(data, ["Артикул ТД", "article_td", "manufacturer_article"]),
            "raw_image": self._first(data, ["Зображення товару", "image_url", "images", "photo", "photo_url"]),
        }

    def _extract_multi(self, payload: dict[str, Any], keys: tuple[str, ...]) -> str:
        data = payload if isinstance(payload, dict) else {}
        for key in keys:
            val = data.get(key)
            if isinstance(val, list):
                for item in val:
                    text = str(item or "").strip()
                    if text:
                        return text
            text = str(val or "").strip()
            if text:
                return text
        return ""

    def _first(self, payload: dict[str, Any], keys: list[str]) -> str:
        for key in keys:
            text = str(payload.get(key) or "").strip()
            if text:
                return text
        return ""

    def _extract_article_from_text(self, value: str) -> str:
        text = str(value or "")
        if not text:
            return ""
        patterns = [
            r"\b[A-Z]{1,5}[\-\s]?[0-9]{2,}[A-Z0-9\-/]*\b",
            r"\b[0-9]{4,}[A-Z]{1,3}\b",
        ]
        upper = text.upper()
        for pattern in patterns:
            match = re.search(pattern, upper)
            if match:
                return str(match.group(0)).strip()
        return ""

    def _build_article_candidates(
        self,
        *,
        deterministic_exact_only: bool,
        canonical_article: str,
        remote_stored_article: str,
        manufacturer_article_candidate: str,
        supplier_article_candidate: str,
        external_sku_candidate: str,
        article_from_name_candidate: str,
        article_from_description_candidate: str,
    ) -> list[tuple[str, str]]:
        if deterministic_exact_only:
            seed = [
                ("canonical_article_candidate", canonical_article),
                ("remote_stored_article_candidate", remote_stored_article),
                ("manufacturer_article_candidate", manufacturer_article_candidate),
                ("supplier_article_candidate", supplier_article_candidate),
            ]
        else:
            seed = [
                ("manufacturer_article_candidate", manufacturer_article_candidate),
                ("supplier_article_candidate", supplier_article_candidate),
                ("external_sku_candidate", external_sku_candidate),
                ("article_from_name_candidate", article_from_name_candidate),
                ("article_from_description_candidate", article_from_description_candidate),
            ]

        out: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for source_name, candidate_value in seed:
            raw_value = str(candidate_value or "").strip()
            if not raw_value:
                continue
            normalized_candidate = self._normalize_candidate(raw_value)
            key = (source_name, normalized_candidate)
            if not normalized_candidate or key in seen:
                continue
            seen.add(key)
            out.append((source_name, raw_value))
        return out

    def _semantic_status(self, *, brand: str, text: str) -> str:
        brand_up = str(brand or "").strip().upper()
        norm_text = " ".join(str(text or "").lower().split())
        has_paint = any(token in norm_text for token in self.PAINT_TOKENS)
        has_part = any(token in norm_text for token in self.PART_TOKENS)

        if brand_up in {"MITKA", "CS SYSTEM"} and has_paint:
            return "conflict"
        if brand_up in self.NON_AUTO_BRANDS and has_paint and not has_part:
            return "conflict"
        if has_part:
            return "compatible"
        if has_paint:
            return "conflict"
        return "unclear"

    def _normalize_candidate(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return self.article_normalizer.normalize(text).normalized or normalize_article(text)

    def _resolve_article_columns(self, *, table: str) -> dict[str, str | None]:
        columns = sorted(self.storage.get_local_columns(table))
        return {
            "supplier": find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id", "supplier"]),
            "article": find_column_name(
                columns,
                [
                    "DataSupplierArticleNumber",
                    "datasupplierarticlenumber",
                    "articleNumber",
                    "articlenumber",
                    "article",
                    "number",
                ],
            ),
            "title": find_column_name(columns, ["Description", "description", "articleName", "name", "title"]),
        }

    def _resolve_supplier_columns(self, *, local: bool) -> dict[str, str | None]:
        columns = sorted(
            self.storage.get_local_columns("suppliers") if local else self.storage.get_remote_columns("suppliers")
        )
        return {
            "id": find_column_name(columns, ["id", "supplierId", "supplierid"]),
            "description": find_column_name(columns, ["description", "Description", "name", "Name"]),
            "matchcode": find_column_name(columns, ["matchcode", "Matchcode", "MatchCode"]),
        }

    def _find_article_local(self, *, supplier_id: int, article_candidate: str) -> tuple[str, str, str] | None:
        key = (int(supplier_id), str(article_candidate))
        if key in self._local_article_cache:
            cached = self._local_article_cache[key]
            return cached if isinstance(cached, tuple) else None
        hit = self._find_article(
            table="article_numbers",
            columns_map=self._article_numbers_columns,
            supplier_id=supplier_id,
            article_candidate=article_candidate,
            remote=False,
        )
        if hit is None:
            hit = self._find_article(
                table="articles",
                columns_map=self._articles_columns,
                supplier_id=supplier_id,
                article_candidate=article_candidate,
                remote=False,
            )
        self._local_article_cache[key] = hit if hit is not None else _MISS
        return hit

    def _find_article_remote(self, *, supplier_id: int, article_candidate: str) -> tuple[str, str, str] | None:
        key = (int(supplier_id), str(article_candidate))
        if key in self._remote_article_cache:
            cached = self._remote_article_cache[key]
            return cached if isinstance(cached, tuple) else None
        hit = self._find_article(
            table="article_numbers",
            columns_map=self._article_numbers_columns,
            supplier_id=supplier_id,
            article_candidate=article_candidate,
            remote=True,
        )
        if hit is None:
            hit = self._find_article(
                table="articles",
                columns_map=self._articles_columns,
                supplier_id=supplier_id,
                article_candidate=article_candidate,
                remote=True,
            )
        self._remote_article_cache[key] = hit if hit is not None else _MISS
        return hit

    def _find_article(
        self,
        *,
        table: str,
        columns_map: dict[str, str | None],
        supplier_id: int,
        article_candidate: str,
        remote: bool,
    ) -> tuple[str, str, str] | None:
        supplier_column = columns_map.get("supplier")
        article_column = columns_map.get("article")
        title_column = columns_map.get("title")
        if not supplier_column or not article_column:
            return None
        variants = tuple(self.article_normalizer.normalize(article_candidate).search_variants or (article_candidate,))
        methods = (
            self.storage.fetch_remote_rows_exact if remote else self.storage.fetch_local_rows
        )
        for variant in variants[:8]:
            filters = {supplier_column: int(supplier_id), article_column: variant}
            rows = methods(table=table, filters=filters, limit=1)
            if rows:
                row = rows[0]
                article_number = str(row.get(article_column) or "").strip()
                title = str(row.get(title_column) or "").strip() if title_column else ""
                return str(supplier_id), article_number, title
        return None

    def _resolve_remote_supplier_candidates(self, *, raw_brand: str, normalized_brand: str) -> tuple[SupplierBrandCandidate, ...]:
        cache_key = normalized_brand
        if cache_key in self._remote_supplier_cache:
            return tuple(self._remote_supplier_cache[cache_key])

        remote_columns = self._ensure_remote_supplier_columns()
        if remote_columns is None:
            self._remote_supplier_cache[cache_key] = []
            return ()

        id_col = remote_columns.get("id")
        desc_col = remote_columns.get("description")
        match_col = remote_columns.get("matchcode")
        if not id_col:
            self._remote_supplier_cache[cache_key] = []
            return ()

        brand_values = [item for item in {str(raw_brand or "").strip(), str(normalized_brand or "").strip()} if item]
        if not brand_values:
            self._remote_supplier_cache[cache_key] = []
            return ()

        candidates: list[SupplierBrandCandidate] = []
        for value in brand_values:
            if desc_col:
                for row in self.storage.fetch_remote_rows_exact(table="suppliers", filters={desc_col: value}, limit=25):
                    cand = self._supplier_candidate_from_row(row, id_col=id_col, desc_col=desc_col, match_col=match_col, confidence=0.95, reason="remote_description_exact")
                    if cand:
                        candidates.append(cand)
            if match_col:
                for row in self.storage.fetch_remote_rows_exact(table="suppliers", filters={match_col: value}, limit=25):
                    cand = self._supplier_candidate_from_row(row, id_col=id_col, desc_col=desc_col, match_col=match_col, confidence=1.0, reason="remote_matchcode_exact")
                    if cand:
                        candidates.append(cand)

        if not candidates:
            relaxed = re.sub(r"[\W_]+", "", normalized_brand or "", flags=re.UNICODE)
            if relaxed:
                if desc_col:
                    for row in self.storage.fetch_remote_rows_like(table="suppliers", column=desc_col, value=relaxed, limit=50):
                        cand = self._supplier_candidate_from_row(row, id_col=id_col, desc_col=desc_col, match_col=match_col, confidence=0.75, reason="remote_description_like")
                        if cand:
                            candidates.append(cand)
                if match_col:
                    for row in self.storage.fetch_remote_rows_like(table="suppliers", column=match_col, value=relaxed, limit=50):
                        cand = self._supplier_candidate_from_row(row, id_col=id_col, desc_col=desc_col, match_col=match_col, confidence=0.8, reason="remote_matchcode_like")
                        if cand:
                            candidates.append(cand)

        deduped: dict[int, SupplierBrandCandidate] = {}
        for item in candidates:
            current = deduped.get(int(item.supplier_id))
            if current is None or item.confidence > current.confidence:
                deduped[int(item.supplier_id)] = item

        result = sorted(deduped.values(), key=lambda item: (-item.confidence, item.supplier_id))[:10]
        self._remote_supplier_cache[cache_key] = result
        return tuple(result)

    def _ensure_remote_supplier_columns(self) -> dict[str, str | None] | None:
        if self._remote_suppliers_columns is not None:
            return self._remote_suppliers_columns
        try:
            self._remote_suppliers_columns = self._resolve_supplier_columns(local=False)
        except (AutoDbProRemoteClientError, Exception):  # noqa: BLE001
            self._remote_suppliers_columns = None
        return self._remote_suppliers_columns

    def _supplier_candidate_from_row(
        self,
        row: dict[str, Any],
        *,
        id_col: str,
        desc_col: str | None,
        match_col: str | None,
        confidence: float,
        reason: str,
    ) -> SupplierBrandCandidate | None:
        try:
            sid = int(row.get(id_col))
        except (TypeError, ValueError):
            return None
        return SupplierBrandCandidate(
            supplier_id=sid,
            supplier_description=str(row.get(desc_col) or "").strip() if desc_col else "",
            supplier_matchcode=str(row.get(match_col) or "").strip() if match_col else "",
            confidence=confidence,
            reason=reason,
        )

    def _safe_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


def summarize_rows(rows: list[UnlinkedLinkCandidateRow]) -> AuditSummary:
    rec_counter: dict[str, int] = {}
    for row in rows:
        rec_counter[row.recommendation] = rec_counter.get(row.recommendation, 0) + 1
    return AuditSummary(
        total_unlinked=len(rows),
        safe_auto_link_candidates=rec_counter.get("safe_auto_link_candidate", 0),
        safe_article_variant_candidates=rec_counter.get("safe_article_variant_candidate", 0),
        brand_alias_candidates=rec_counter.get("brand_alias_candidate", 0),
        external_sku_candidates=rec_counter.get("external_sku_candidate", 0),
        article_from_name_candidates=rec_counter.get("article_from_name_candidate", 0),
        manual_mapping_needed=rec_counter.get("manual_mapping_needed", 0),
        non_auto_or_supplier_only=rec_counter.get("non_auto_or_supplier_only", 0),
        remote_not_found=rec_counter.get("remote_not_found", 0),
        unsafe_ambiguous=rec_counter.get("unsafe_ambiguous", 0),
        semantic_conflict=sum(1 for item in rows if item.semantic_status == "conflict"),
    )
