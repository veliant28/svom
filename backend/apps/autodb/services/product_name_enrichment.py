from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from hashlib import sha1
import re
from typing import Any

from django.db.models import Q, QuerySet

from apps.autodb.services.column_helpers import find_column_name, find_value
from apps.autodb.services.product_name_translation import ProductNameTranslationService
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.catalog.models import Product
from apps.catalog.services.product_management import sanitize_product_name
from apps.supplier_imports.models import SupplierRawOffer


@dataclass(frozen=True)
class ProductNameEnrichmentResult:
    product_id: str
    status: str
    old_name: str
    supplier_raw_name: str
    autodb_source_title: str
    new_name_uk: str
    new_name_ru: str
    new_name_en: str
    name_source: str
    name_source_hash: str
    translation_status: str
    translation_error: str = ""
    source_title_before_cleanup: str = ""
    source_title_after_cleanup: str = ""
    source_reason: str = ""
    supplier_fallback_used: bool = False


@dataclass(frozen=True)
class ProductNameSourceDiagnostics:
    source_kind: str
    source_reason: str
    source_title_before_cleanup: str
    source_title_after_cleanup: str
    supplier_fallback_used: bool
    supplier_fallback_reason: str
    suffix_candidates: tuple[str, ...]
    article_row: dict[str, Any]
    article_number_row: dict[str, Any]
    article_prd_rows: tuple[dict[str, Any], ...]
    article_links_rows: tuple[dict[str, Any], ...]
    prd_rows: tuple[dict[str, Any], ...]
    article_inf_rows: tuple[dict[str, Any], ...]
    raw_offer_rows: tuple[dict[str, Any], ...]


class AutoDbProductNameEnrichmentService:
    _letter_re = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ]")
    _placeholder_artifact_re = re.compile(r"(?:auto\s*db|autodb|автодб)", re.IGNORECASE)
    _conflicting_name_families: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
        (
            (
                "амортиз",
                "shock absorber",
            ),
            (
                "предглуш",
                "глушител",
                "глушник",
                "выхлоп",
                "вихлоп",
                "выпуск",
                "резонатор",
                "silencer",
                "muffler",
                "exhaust",
            ),
        ),
    )

    def __init__(
        self,
        *,
        storage: AutoDbRawCloneStorage | None = None,
        translator: ProductNameTranslationService | None = None,
    ):
        self.storage = storage or AutoDbRawCloneStorage()
        self.translator = translator or ProductNameTranslationService()

    def enrich_product(
        self,
        *,
        product: Product,
        dry_run: bool,
        only_missing_translations: bool = False,
    ) -> ProductNameEnrichmentResult:
        old_name = str(product.name or "")
        if bool(product.name_manually_locked):
            return ProductNameEnrichmentResult(
                product_id=str(product.id),
                status="skipped_manual_locked",
                old_name=old_name,
                supplier_raw_name="",
                autodb_source_title="",
                new_name_uk=product.name_uk,
                new_name_ru=product.name_ru,
                new_name_en=product.name_en,
                name_source=Product.NAME_SOURCE_MANUAL,
                name_source_hash=str(product.name_source_hash or ""),
                translation_status=Product.NAME_TRANSLATION_MANUAL_LOCKED,
            )

        supplier_raw_name = self._resolve_supplier_raw_name(product=product)
        if not product.autodb_supplier_id or not str(product.autodb_article_number or "").strip():
            return ProductNameEnrichmentResult(
                product_id=str(product.id),
                status="skipped_no_autodb_link",
                old_name=old_name,
                supplier_raw_name=supplier_raw_name,
                autodb_source_title="",
                new_name_uk=product.name_uk,
                new_name_ru=product.name_ru,
                new_name_en=product.name_en,
                name_source=str(product.name_source or ""),
                name_source_hash=str(product.name_source_hash or ""),
                translation_status=str(product.name_translation_status or ""),
            )

        diagnostics = self.build_diagnostics(product=product)
        source_title = diagnostics.source_title_before_cleanup
        clean_title = diagnostics.source_title_after_cleanup
        source_kind = diagnostics.source_kind

        if not source_title or not clean_title:
            return ProductNameEnrichmentResult(
                product_id=str(product.id),
                status="skipped_no_source_title",
                old_name=old_name,
                supplier_raw_name=supplier_raw_name,
                autodb_source_title=source_title,
                new_name_uk=product.name_uk,
                new_name_ru=product.name_ru,
                new_name_en=product.name_en,
                name_source=str(product.name_source or ""),
                name_source_hash=str(product.name_source_hash or ""),
                translation_status=str(product.name_translation_status or ""),
                source_title_before_cleanup=source_title,
                source_title_after_cleanup=clean_title,
                source_reason=diagnostics.source_reason,
                supplier_fallback_used=diagnostics.supplier_fallback_used,
            )

        source_hash = sha1(f"{source_kind}:{clean_title}".encode("utf-8")).hexdigest()  # noqa: S324
        has_placeholder_artifacts = self._has_placeholder_artifacts(
            name_uk=str(product.name_uk or ""),
            name_en=str(product.name_en or ""),
        )
        has_latin_suffix_quality_issue = self._has_latin_suffix_quality_issue(
            source_title=clean_title,
            name_uk=str(product.name_uk or ""),
            name_ru=str(product.name_ru or ""),
            name_en=str(product.name_en or ""),
        )
        has_dictionary_mismatch = self._has_dictionary_mismatch(
            source_title=clean_title,
            name_uk=str(product.name_uk or ""),
            name_ru=str(product.name_ru or ""),
            name_en=str(product.name_en or ""),
        )
        needs_translation = (
            not product.name_uk
            or not product.name_ru
            or not product.name_en
            or (product.name_source_hash or "") != source_hash
            or has_placeholder_artifacts
            or has_latin_suffix_quality_issue
            or has_dictionary_mismatch
        )
        if only_missing_translations and not (not product.name_uk or not product.name_ru or not product.name_en):
            return ProductNameEnrichmentResult(
                product_id=str(product.id),
                status="skipped_translations_present",
                old_name=old_name,
                supplier_raw_name=supplier_raw_name,
                autodb_source_title=source_title,
                new_name_uk=product.name_uk,
                new_name_ru=product.name_ru,
                new_name_en=product.name_en,
                name_source=str(product.name_source or ""),
                name_source_hash=str(product.name_source_hash or ""),
                translation_status=str(product.name_translation_status or ""),
                source_title_before_cleanup=source_title,
                source_title_after_cleanup=clean_title,
                source_reason=diagnostics.source_reason,
                supplier_fallback_used=diagnostics.supplier_fallback_used,
            )

        if not needs_translation and not only_missing_translations:
            return ProductNameEnrichmentResult(
                product_id=str(product.id),
                status="skipped_hash_unchanged",
                old_name=old_name,
                supplier_raw_name=supplier_raw_name,
                autodb_source_title=source_title,
                new_name_uk=product.name_uk,
                new_name_ru=product.name_ru,
                new_name_en=product.name_en,
                name_source=str(product.name_source or ""),
                name_source_hash=str(product.name_source_hash or ""),
                translation_status=str(product.name_translation_status or ""),
                source_title_before_cleanup=source_title,
                source_title_after_cleanup=clean_title,
                source_reason=diagnostics.source_reason,
                supplier_fallback_used=diagnostics.supplier_fallback_used,
            )

        translation = self.translator.translate_product_name(source_text=clean_title)
        name_uk = translation.uk or clean_title
        name_ru = translation.ru or clean_title
        name_en = translation.en or clean_title
        translation_status = translation.status
        translation_error = translation.error

        article_description = sanitize_product_name(
            str(find_value(diagnostics.article_row, ["Description", "description"]) or "")
        )
        if translation_status != "translated" and article_description:
            base_part = sanitize_product_name(self._strip_trailing_exact_candidate(clean_title, article_description))
            if base_part and base_part != clean_title:
                base_translation = self.translator.translate_product_name(source_text=base_part)
                if base_translation.status == "translated":
                    name_uk = self._combine_base_and_description(
                        base=(base_translation.uk or base_part),
                        description=article_description,
                    )
                    name_ru = self._combine_base_and_description(
                        base=(base_translation.ru or base_part),
                        description=article_description,
                    )
                    name_en = self._combine_base_and_description(
                        base=(base_translation.en or base_part),
                        description=article_description,
                    )
                    translation_status = "translated"
                    translation_error = ""

        if not dry_run:
            product.name = name_uk or clean_title
            product.name_uk = name_uk
            product.name_ru = name_ru
            product.name_en = name_en
            product.name_source = source_kind
            # Keep original source text before cleanup for traceability.
            product.name_source_text = source_title
            product.name_source_hash = source_hash
            product.name_translation_status = translation_status
            product.name_translation_error = translation_error
            product.save(
                update_fields=(
                    "name",
                    "name_uk",
                    "name_ru",
                    "name_en",
                    "name_source",
                    "name_source_text",
                    "name_source_hash",
                    "name_translation_status",
                    "name_translation_error",
                    "updated_at",
                )
            )

        return ProductNameEnrichmentResult(
            product_id=str(product.id),
            status="updated",
            old_name=old_name,
            supplier_raw_name=supplier_raw_name,
            autodb_source_title=source_title,
            new_name_uk=name_uk,
            new_name_ru=name_ru,
            new_name_en=name_en,
            name_source=source_kind,
            name_source_hash=source_hash,
            translation_status=translation_status,
            translation_error=translation_error,
            source_title_before_cleanup=source_title,
            source_title_after_cleanup=clean_title,
            source_reason=diagnostics.source_reason,
            supplier_fallback_used=diagnostics.supplier_fallback_used,
        )

    def _has_placeholder_artifacts(self, *, name_uk: str, name_en: str) -> bool:
        return bool(
            self._placeholder_artifact_re.search(name_uk or "")
            or self._placeholder_artifact_re.search(name_en or "")
        )

    def _has_latin_suffix_quality_issue(self, *, source_title: str, name_uk: str, name_ru: str, name_en: str) -> bool:
        expected = self.translator._apply_headword_translation_for_latin_suffix(
            source_text=source_title,
            uk=source_title,
            ru=source_title,
            en=source_title,
        )
        if expected == (source_title, source_title, source_title):
            return False
        current = (
            sanitize_product_name(name_uk or ""),
            sanitize_product_name(name_ru or ""),
            sanitize_product_name(name_en or ""),
        )
        return current != expected

    def _has_dictionary_mismatch(self, *, source_title: str, name_uk: str, name_ru: str, name_en: str) -> bool:
        load_index = getattr(self.translator, "_load_translation_index", None)
        normalize_key = getattr(self.translator, "_normalize_key", None)
        if not callable(load_index) or not callable(normalize_key):
            return False
        try:
            mapped = load_index().get(normalize_key(source_title))
        except Exception:  # noqa: BLE001
            return False
        if not mapped:
            return False
        if not isinstance(mapped, (tuple, list)) or len(mapped) < 3:
            return False
        current = (
            sanitize_product_name(name_uk or ""),
            sanitize_product_name(name_ru or ""),
            sanitize_product_name(name_en or ""),
        )
        expected = tuple(sanitize_product_name(str(item or "")) for item in mapped)
        return current != expected

    def build_diagnostics(self, *, product: Product) -> ProductNameSourceDiagnostics:
        supplier_id = int(product.autodb_supplier_id or 0)
        article_number = str(product.autodb_article_number or "")
        supplier_raw_name = self._resolve_supplier_raw_name(product=product)

        article_row = self._find_article_row(supplier_id=supplier_id, article_number=article_number) or {}
        article_number_row = self._find_article_number_row(supplier_id=supplier_id, article_number=article_number) or {}
        article_prd_rows = tuple(self._find_article_prd_rows(supplier_id=supplier_id, article_number=article_number))
        article_links_rows = tuple(self._find_article_links_rows(supplier_id=supplier_id, article_number=article_number))
        prd_rows = tuple(self._find_prd_rows(article_prd_rows=article_prd_rows, article_links_rows=article_links_rows))
        article_inf_rows = tuple(self._find_article_inf_rows(supplier_id=supplier_id, article_number=article_number))
        raw_offer_rows = tuple(self._collect_raw_offer_rows(product=product))

        suffix_candidates = self._collect_suffix_candidates(
            product=product,
            raw_offer_rows=raw_offer_rows,
        )

        source_candidates: list[tuple[str, str, str]] = []
        article_description_for_name = sanitize_product_name(str(find_value(article_row, ["Description", "description"]) or ""))
        for row in prd_rows:
            normalized = sanitize_product_name(str(find_value(row, ["normalizeddescription", "NormalizedDescription", "description"]) or ""))
            description = sanitize_product_name(str(find_value(row, ["description", "Description"]) or ""))
            combined = self._combine_base_and_description(base=normalized, description=description)
            if combined:
                source_candidates.append((Product.NAME_SOURCE_AUTODB_PRO, combined, "prd.normalized_plus_description"))
            if normalized:
                source_candidates.append((Product.NAME_SOURCE_AUTODB_PRO, normalized, "prd.normalizeddescription"))
            if description and description != normalized:
                source_candidates.append((Product.NAME_SOURCE_AUTODB_PRO, description, "prd.description"))

        normalized_description = sanitize_product_name(str(find_value(article_row, ["NormalizedDescription", "normalizeddescription"]) or ""))
        description = sanitize_product_name(str(find_value(article_row, ["Description", "description"]) or ""))
        combined = self._combine_base_and_description(base=normalized_description, description=description)
        if combined:
            source_candidates.append((Product.NAME_SOURCE_AUTODB_PRO, combined, "articles.normalized_plus_description"))
        if normalized_description:
            source_candidates.append((Product.NAME_SOURCE_AUTODB_PRO, normalized_description, "articles.normalized_description"))
        if description:
            source_candidates.append((Product.NAME_SOURCE_AUTODB_PRO, description, "articles.description"))

        for row in article_inf_rows:
            inf_text = sanitize_product_name(str(find_value(row, ["InformationText", "informationtext", "description"]) or ""))
            if inf_text and 3 <= len(inf_text) <= 120:
                source_candidates.append((Product.NAME_SOURCE_AUTODB_PRO, inf_text, "article_inf.information_text"))

        if supplier_raw_name:
            source_candidates.append((Product.NAME_SOURCE_SUPPLIER_FALLBACK, supplier_raw_name, "supplier_raw_offer.product_name"))

        chosen_kind = ""
        chosen_reason = ""
        title_before_cleanup = ""
        title_after_cleanup = ""

        for kind, title, reason in source_candidates:
            cleaned = self._clean_title(
                title=title,
                suffix_candidates=suffix_candidates,
                is_fallback=(kind == Product.NAME_SOURCE_SUPPLIER_FALLBACK),
            )
            if kind == Product.NAME_SOURCE_AUTODB_PRO and article_description_for_name:
                cleaned = self._combine_base_and_description(
                    base=cleaned,
                    description=article_description_for_name,
                )
            if not self._is_usable_title(cleaned):
                continue
            chosen_kind = kind
            chosen_reason = reason
            title_before_cleanup = sanitize_product_name(title)
            title_after_cleanup = cleaned
            break

        supplier_fallback_used = chosen_kind == Product.NAME_SOURCE_SUPPLIER_FALLBACK
        supplier_fallback_reason = ""
        if supplier_fallback_used:
            supplier_fallback_reason = "autodb_title_missing_or_unusable"

        return ProductNameSourceDiagnostics(
            source_kind=chosen_kind,
            source_reason=chosen_reason,
            source_title_before_cleanup=title_before_cleanup,
            source_title_after_cleanup=title_after_cleanup,
            supplier_fallback_used=supplier_fallback_used,
            supplier_fallback_reason=supplier_fallback_reason,
            suffix_candidates=suffix_candidates,
            article_row=article_row,
            article_number_row=article_number_row,
            article_prd_rows=article_prd_rows,
            article_links_rows=article_links_rows,
            prd_rows=prd_rows,
            article_inf_rows=article_inf_rows,
            raw_offer_rows=raw_offer_rows,
        )

    def _find_article_row(self, *, supplier_id: int, article_number: str) -> dict | None:
        if supplier_id <= 0 or not article_number:
            return None
        self.storage.ensure_table("articles")
        columns = list(self.storage.get_local_columns("articles"))
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"],
        )
        if not supplier_column or not article_column:
            return None
        rows = self.storage.fetch_local_rows(
            table="articles",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=1,
            columns=columns,
        )
        if rows:
            return rows[0]
        return None

    def _find_article_number_row(self, *, supplier_id: int, article_number: str) -> dict | None:
        if supplier_id <= 0 or not article_number:
            return None
        self.storage.ensure_table("article_numbers")
        columns = list(self.storage.get_local_columns("article_numbers"))
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"],
        )
        if not supplier_column or not article_column:
            return None
        rows = self.storage.fetch_local_rows(
            table="article_numbers",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=1,
            columns=columns,
        )
        if rows:
            return rows[0]
        return None

    def _find_article_prd_rows(self, *, supplier_id: int, article_number: str) -> list[dict[str, Any]]:
        if supplier_id <= 0 or not article_number:
            return []
        self.storage.ensure_table("article_prd")
        columns = list(self.storage.get_local_columns("article_prd"))
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"],
        )
        if not supplier_column or not article_column:
            return []
        return self.storage.fetch_local_rows(
            table="article_prd",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=200,
            columns=columns,
        )

    def _find_article_links_rows(self, *, supplier_id: int, article_number: str) -> list[dict[str, Any]]:
        if supplier_id <= 0 or not article_number:
            return []
        self.storage.ensure_table("article_links")
        columns = list(self.storage.get_local_columns("article_links"))
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"],
        )
        if not supplier_column or not article_column:
            return []
        return self.storage.fetch_local_rows(
            table="article_links",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=200,
            columns=columns,
        )

    def _find_prd_rows(
        self,
        *,
        article_prd_rows: tuple[dict[str, Any], ...],
        article_links_rows: tuple[dict[str, Any], ...],
    ) -> list[dict[str, Any]]:
        self.storage.ensure_table("prd")
        columns = list(self.storage.get_local_columns("prd"))
        if not columns:
            return []
        id_column = find_column_name(columns, ["id", "productId", "productid", "ProductId"]) or "id"

        product_ids: list[int] = []
        for row in list(article_prd_rows) + list(article_links_rows):
            value = find_value(row, ["productId", "productid", "ProductId", "id", "prdid"])
            try:
                pid = int(value)
            except (TypeError, ValueError):
                continue
            if pid not in product_ids:
                product_ids.append(pid)

        if not product_ids:
            return []

        return self.storage.fetch_local_rows_in(
            table="prd",
            column=id_column,
            values=product_ids,
            limit=200,
            columns=columns,
        )

    def _find_article_inf_rows(self, *, supplier_id: int, article_number: str) -> list[dict[str, Any]]:
        if supplier_id <= 0 or not article_number:
            return []
        self.storage.ensure_table("article_inf")
        columns = list(self.storage.get_local_columns("article_inf"))
        if not columns:
            return []
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"],
        )
        if not supplier_column or not article_column:
            return []
        return self.storage.fetch_local_rows(
            table="article_inf",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=200,
            columns=columns,
        )

    def _resolve_supplier_raw_name(self, *, product: Product) -> str:
        row = (
            SupplierRawOffer.objects.filter(matched_product=product)
            .order_by("-updated_at")
            .values_list("product_name", flat=True)
            .first()
        )
        return sanitize_product_name(str(row or ""))[:255]

    def _collect_raw_offer_rows(self, *, product: Product) -> list[dict[str, Any]]:
        rows = (
            SupplierRawOffer.objects.filter(Q(matched_product=product) | Q(article__iexact=product.article) | Q(external_sku__iexact=product.sku))
            .order_by("-updated_at")
            .values("id", "article", "external_sku", "normalized_article", "product_name", "raw_payload")[:20]
        )
        return [dict(item) for item in rows]

    def _collect_suffix_candidates(self, *, product: Product, raw_offer_rows: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
        values: list[str] = [
            str(product.autodb_article_number or ""),
            str(product.article or ""),
            str(product.sku or ""),
        ]
        for row in raw_offer_rows:
            values.extend(
                [
                    str(row.get("article") or ""),
                    str(row.get("external_sku") or ""),
                    str((row.get("raw_payload") or {}).get("Артикул") or ""),
                    str((row.get("raw_payload") or {}).get("Артикул UTR") or ""),
                    str((row.get("raw_payload") or {}).get("Артикул ТД") or ""),
                    str((row.get("raw_payload") or {}).get("article_td") or ""),
                    str((row.get("raw_payload") or {}).get("manufacturer_article") or ""),
                ]
            )

        out: list[str] = []
        for item in values:
            value = sanitize_product_name(item)
            if not value:
                continue
            if value.upper() not in {x.upper() for x in out}:
                out.append(value)

        out.sort(key=lambda x: len(x), reverse=True)
        return tuple(out)

    def _clean_title(self, *, title: str, suffix_candidates: tuple[str, ...], is_fallback: bool) -> str:
        text = str(title or "")
        text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        text = sanitize_product_name(text)
        if not text:
            return ""

        if is_fallback:
            text = re.sub(r"^\s*[0-9]{3,}\s+", "", text).strip()
            text = sanitize_product_name(text)

        cleaned = text
        for candidate in suffix_candidates:
            cleaned = self._strip_trailing_exact_candidate(cleaned, candidate)
            cleaned = sanitize_product_name(cleaned)
        return cleaned[:255]

    def _strip_trailing_exact_candidate(self, title: str, candidate: str) -> str:
        text = str(title or "").strip()
        suffix = str(candidate or "").strip()
        if not text or not suffix:
            return text
        if len(text) <= len(suffix):
            return text
        if not text.upper().endswith(suffix.upper()):
            return text

        cut = len(text) - len(suffix)
        prefix = text[:cut].rstrip()
        if not prefix:
            return text

        boundary_idx = cut - 1
        if boundary_idx >= 0:
            boundary_char = text[boundary_idx]
            if boundary_char.isalnum():
                return text

        prefix = prefix.rstrip(" -–—:/|,;#()[]{}")
        if not prefix:
            return text
        if not self._letter_re.search(prefix):
            return text
        return prefix

    def _is_usable_title(self, value: str) -> bool:
        text = sanitize_product_name(value)
        if not text:
            return False
        if len(text) < 3:
            return False
        if not self._letter_re.search(text):
            return False
        return True

    def _combine_base_and_description(self, *, base: str, description: str) -> str:
        base_clean = sanitize_product_name(base)
        description_clean = sanitize_product_name(description)
        if not base_clean and not description_clean:
            return ""
        if not base_clean:
            return description_clean
        if not description_clean:
            return base_clean

        base_lower = base_clean.lower()
        description_lower = description_clean.lower()
        if description_lower in base_lower:
            return base_clean
        if base_lower in description_lower:
            return description_clean
        if self._looks_like_duplicate_prefix(base_clean=base_clean, description_clean=description_clean):
            return description_clean
        if self._looks_like_conflicting_headwords(base_clean=base_clean, description_clean=description_clean):
            return description_clean
        return sanitize_product_name(f"{base_clean} {description_clean}")[:255]

    def _looks_like_duplicate_prefix(self, *, base_clean: str, description_clean: str) -> bool:
        head = description_clean
        for separator in (",", ";", ":", "(", ")", "-", "–", "—"):
            if separator in head:
                head = head.split(separator, 1)[0]
        head = sanitize_product_name(head)
        if not head:
            return False
        normalized_base = self._normalize_compare_text(base_clean)
        normalized_head = self._normalize_compare_text(head)
        if not normalized_base or not normalized_head:
            return False
        if len(normalized_head) >= 10 and normalized_base.startswith(f"{normalized_head} "):
            return True
        if normalized_base == normalized_head:
            return True
        ratio = SequenceMatcher(None, normalized_base, normalized_head).ratio()
        return ratio >= 0.84

    def _normalize_compare_text(self, value: str) -> str:
        normalized = sanitize_product_name(value).lower()
        normalized = normalized.replace("ё", "е").replace("ъ", "")
        normalized = normalized.replace("ь", "")
        normalized = re.sub(r"[^a-zа-я0-9 ]+", " ", normalized)
        normalized = sanitize_product_name(normalized)
        return normalized

    def _looks_like_conflicting_headwords(self, *, base_clean: str, description_clean: str) -> bool:
        base_lower = sanitize_product_name(base_clean).lower()
        description_lower = sanitize_product_name(description_clean).lower()
        if not base_lower or not description_lower:
            return False
        for base_markers, description_markers in self._conflicting_name_families:
            if any(marker in base_lower for marker in base_markers) and any(
                marker in description_lower for marker in description_markers
            ):
                return True
        return False

    def build_queryset(
        self,
        *,
        only_linked: bool,
        only_missing_translations: bool,
        product_id: str,
    ) -> QuerySet[Product]:
        qs = Product.objects.select_related("category").order_by("id")
        if only_linked:
            qs = qs.filter(autodb_supplier_id__isnull=False).exclude(autodb_article_number="")
        if only_missing_translations:
            qs = qs.filter(Q(name_uk="") | Q(name_ru="") | Q(name_en=""))
        if product_id:
            qs = qs.filter(pk=product_id)
        return qs
