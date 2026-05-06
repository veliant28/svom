from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from typing import Any

from apps.autodb.services.article_variant_diagnostics import (
    ArticleVariantDiagnosticsReport,
    ArticleVariantDiagnosticsRow,
    AutoDbArticleVariantDiagnosticsService,
    BrandVariantDiagnostics,
)
from apps.autodb.services.article_variant_apply_classifier import ArticleVariantApplyClassifier
from apps.autodb.services.column_helpers import find_column_name, find_value
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.compatibility.models import ProductFitment
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ArticleVariantCheckpointRow:
    supplier: str
    raw_brand: str
    normalized_brand: str
    resolved_supplier_id: int | None
    raw_article: str
    normalized_article: str
    corrected_article_candidate: str
    product_id: str
    current_autodb_article_key: str
    proposed_autodb_article_key: str
    status: str
    confidence: float
    reason: str
    raw_product_name: str
    autodb_title: str
    autodb_category: str
    recommendation: str
    current_quality_status: str
    recommended_action: str
    sample_offer_id: str
    related_to_known_suspicious_product: bool = False


@dataclass(frozen=True)
class ArticleVariantCheckpointBrandSummary:
    raw_brand: str
    normalized_brand: str
    resolved_supplier_id: int | None
    total_pairs: int
    linked_before_or_current: int
    variant_would_find_total: int
    already_linked_same_key: int
    already_linked_conflicting_key: int
    remaining_safe_to_apply: int
    needs_manual_review: int
    suspicious: int
    semantic_conflict: int
    exact_not_found: int
    skipped_low_confidence: int
    non_auto_ignore: int
    recommended_next_action: str


@dataclass(frozen=True)
class ArticleVariantCheckpointRecommendation:
    recommended_next_brand: str
    recommended_limit: int
    expected_safe_candidates: int
    command_to_run_next_dry_run: str
    command_to_run_next_real: str


@dataclass(frozen=True)
class PolmoReviewSummary:
    safe_to_apply: int
    suspicious: int
    semantic_conflict: int
    already_linked_same_key: int
    already_linked_conflicting_key: int
    related_to_known_suspicious_products: int
    exhaust_to_shock_risk: int
    recommended_next_action: str
    examples: tuple[ArticleVariantCheckpointRow, ...]


@dataclass(frozen=True)
class ArticleVariantCheckpointReport:
    supplier: str
    limit: int
    min_confidence: float
    diagnostics_report: ArticleVariantDiagnosticsReport
    checkpoint_rows: tuple[ArticleVariantCheckpointRow, ...]
    brand_summaries: tuple[ArticleVariantCheckpointBrandSummary, ...]
    recommended_next: ArticleVariantCheckpointRecommendation
    polmo_summary: PolmoReviewSummary


class AutoDbArticleVariantApplyCheckpointService:
    STATUS_ALREADY_LINKED_SAME_KEY = ArticleVariantApplyClassifier.STATUS_ALREADY_LINKED_SAME_KEY
    STATUS_ALREADY_LINKED_CONFLICTING_KEY = ArticleVariantApplyClassifier.STATUS_ALREADY_LINKED_CONFLICTING_KEY
    STATUS_SAFE_TO_APPLY = ArticleVariantApplyClassifier.STATUS_SAFE_TO_APPLY
    STATUS_SKIPPED_SUSPICIOUS = ArticleVariantApplyClassifier.STATUS_SKIPPED_SUSPICIOUS
    STATUS_SKIPPED_SEMANTIC_CONFLICT = ArticleVariantApplyClassifier.STATUS_SKIPPED_SEMANTIC_CONFLICT
    STATUS_SKIPPED_LOW_CONFIDENCE = ArticleVariantApplyClassifier.STATUS_SKIPPED_LOW_CONFIDENCE
    STATUS_EXACT_NOT_FOUND = ArticleVariantApplyClassifier.STATUS_EXACT_NOT_FOUND
    STATUS_NEEDS_MANUAL_REVIEW = ArticleVariantApplyClassifier.STATUS_NEEDS_MANUAL_REVIEW
    STATUS_NON_AUTO_IGNORE = ArticleVariantApplyClassifier.STATUS_NON_AUTO_IGNORE

    SAFE_RECOMMENDATIONS = ArticleVariantApplyClassifier.SAFE_RECOMMENDATIONS
    TARGET_BRANDS = (
        "WIX FILTERS",
        "FRAM",
        "ERT",
        "AL-KO",
        "WOKING",
        "AUTOMEGA",
        "FENOX",
        "BOSAL",
        "POLMO",
        "SPIDAN",
    )
    POLMO_NORMALIZED = normalize_brand("POLMO")

    _TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ0-9]{4,}", flags=re.UNICODE)
    _EXHAUST_TOKENS = {"глушник", "глушитель", "резонатор", "выпуск", "вихлоп", "exhaust", "muffler", "silencer"}
    _SHOCK_TOKENS = {"амортизатор", "shock", "absorber", "strut"}

    def __init__(
        self,
        *,
        diagnostics_service: AutoDbArticleVariantDiagnosticsService | None = None,
        storage: AutoDbRawCloneStorage | None = None,
        classifier: ArticleVariantApplyClassifier | None = None,
    ):
        self.diagnostics_service = diagnostics_service or AutoDbArticleVariantDiagnosticsService()
        self.storage = storage or AutoDbRawCloneStorage()
        self.classifier = classifier or ArticleVariantApplyClassifier()

    def build_report(
        self,
        *,
        supplier_code: str,
        limit: int,
        brand_filter: set[str] | None = None,
        batch_size: int = 1000,
        min_confidence: float = 0.9,
    ) -> ArticleVariantCheckpointReport:
        diagnostics = self.diagnostics_service.diagnose(
            supplier_code=supplier_code,
            limit=limit,
            brand_filter=brand_filter,
            batch_size=batch_size,
        )
        checkpoint_rows = self._build_checkpoint_rows(
            diagnostics_rows=diagnostics.diagnostics_rows,
            min_confidence=min_confidence,
        )
        brand_summaries = self._build_brand_summaries(
            diagnostics=diagnostics,
            checkpoint_rows=checkpoint_rows,
            brand_filter=brand_filter,
        )
        recommended_next = self._build_recommendation(
            supplier_code=supplier_code,
            brand_summaries=brand_summaries,
        )
        polmo_summary = self._build_polmo_summary(checkpoint_rows=checkpoint_rows)
        return ArticleVariantCheckpointReport(
            supplier=supplier_code.lower(),
            limit=limit,
            min_confidence=min_confidence,
            diagnostics_report=diagnostics,
            checkpoint_rows=tuple(checkpoint_rows),
            brand_summaries=tuple(brand_summaries),
            recommended_next=recommended_next,
            polmo_summary=polmo_summary,
        )

    def _build_checkpoint_rows(
        self,
        *,
        diagnostics_rows: tuple[ArticleVariantDiagnosticsRow, ...],
        min_confidence: float,
    ) -> list[ArticleVariantCheckpointRow]:
        product_ids = sorted({pid for row in diagnostics_rows for pid in row.matched_product_ids})
        products = {str(item.id): item for item in Product.objects.in_bulk(product_ids).values()}
        quality_map = {
            (str(item.product_id), str(item.autodb_article_key or "").strip()): str(item.status or "")
            for item in AutoDbProductLinkQuality.objects.filter(product_id__in=product_ids)
        }
        excluded_map: Counter[tuple[str, str]] = Counter()
        for row in ProductFitment.objects.filter(product_id__in=product_ids, excluded_from_public_filtering=True).values(
            "product_id",
            "autodb_article_key",
        ):
            excluded_map[(str(row["product_id"]), str(row.get("autodb_article_key") or "").strip())] += 1
        known_suspicious_product_ids = {
            product_id
            for (product_id, article_key), status in quality_map.items()
            if status == AutoDbProductLinkQuality.STATUS_SUSPICIOUS and article_key
        }
        known_suspicious_product_ids.update(
            product_id
            for product_id, article_key in excluded_map
            if article_key
        )

        context_cache: dict[tuple[int | None, str], tuple[str, str]] = {}
        checkpoint_rows: list[ArticleVariantCheckpointRow] = []
        for row in diagnostics_rows:
            if row.matched_product_ids:
                for product_id in row.matched_product_ids:
                    product = products.get(str(product_id))
                    checkpoint_rows.append(
                        self._build_product_checkpoint_row(
                            row=row,
                            product=product,
                            min_confidence=min_confidence,
                            quality_map=quality_map,
                            excluded_map=excluded_map,
                            context_cache=context_cache,
                            known_suspicious_product_ids=known_suspicious_product_ids,
                        )
                    )
            else:
                checkpoint_rows.append(
                    self._build_product_checkpoint_row(
                        row=row,
                        product=None,
                        min_confidence=min_confidence,
                        quality_map=quality_map,
                        excluded_map=excluded_map,
                        context_cache=context_cache,
                        known_suspicious_product_ids=known_suspicious_product_ids,
                    )
                )
        checkpoint_rows.sort(
            key=lambda item: (
                item.raw_brand or "",
                item.status,
                -(item.confidence or 0.0),
                item.raw_article or "",
                item.product_id or "",
            )
        )
        return checkpoint_rows

    def _build_product_checkpoint_row(
        self,
        *,
        row: ArticleVariantDiagnosticsRow,
        product: Product | None,
        min_confidence: float,
        quality_map: dict[tuple[str, str], str],
        excluded_map: Counter[tuple[str, str]],
        context_cache: dict[tuple[int | None, str], tuple[str, str]],
        known_suspicious_product_ids: set[str],
    ) -> ArticleVariantCheckpointRow:
        proposed_article_number = str(row.corrected_article_candidate or "").replace(" ", "").strip()
        proposed_key = f"{row.supplier_id}:{proposed_article_number}" if row.supplier_id and proposed_article_number else ""
        autodb_title, autodb_category = self._lookup_autodb_context(
            supplier_id=row.supplier_id,
            article_number=proposed_article_number,
            fallback_title=row.autodb_title,
            cache=context_cache,
        )
        product_id = str(product.id) if product is not None else ""
        current_key = str(getattr(product, "autodb_article_key", "") or "").strip()
        quality_status = quality_map.get((product_id, current_key), "")
        excluded_count = int(excluded_map.get((product_id, current_key), 0))

        status, reason = self._classify_status(
            row=row,
            product=product,
            proposed_key=proposed_key,
            min_confidence=min_confidence,
            quality_status=quality_status,
            excluded_count=excluded_count,
            autodb_title=autodb_title,
            autodb_category=autodb_category,
        )
        recommended_action = self._recommended_action(
            normalized_brand=row.normalized_brand,
            status=status,
        )

        return ArticleVariantCheckpointRow(
            supplier=row.supplier,
            raw_brand=row.raw_brand,
            normalized_brand=row.normalized_brand,
            resolved_supplier_id=row.supplier_id,
            raw_article=row.raw_article,
            normalized_article=row.normalized_article,
            corrected_article_candidate=proposed_article_number,
            product_id=product_id,
            current_autodb_article_key=current_key,
            proposed_autodb_article_key=proposed_key,
            status=status,
            confidence=row.confidence,
            reason=reason,
            raw_product_name=row.raw_product_name,
            autodb_title=autodb_title,
            autodb_category=autodb_category,
            recommendation=row.recommendation,
            current_quality_status=quality_status,
            recommended_action=recommended_action,
            sample_offer_id=row.sample_offer_id,
            related_to_known_suspicious_product=bool(product_id and product_id in known_suspicious_product_ids),
        )

    def _classify_status(
        self,
        *,
        row: ArticleVariantDiagnosticsRow,
        product: Product | None,
        proposed_key: str,
        min_confidence: float,
        quality_status: str,
        excluded_count: int,
        autodb_title: str,
        autodb_category: str,
    ) -> tuple[str, str]:
        return self.classifier.classify(
            row=row,
            product=product,
            proposed_key=proposed_key,
            min_confidence=min_confidence,
            quality_status=quality_status,
            excluded_count=excluded_count,
            autodb_title=autodb_title,
            autodb_category=autodb_category,
        )

    def _build_brand_summaries(
        self,
        *,
        diagnostics: ArticleVariantDiagnosticsReport,
        checkpoint_rows: list[ArticleVariantCheckpointRow],
        brand_filter: set[str] | None,
    ) -> list[ArticleVariantCheckpointBrandSummary]:
        rows_by_brand: defaultdict[str, list[ArticleVariantCheckpointRow]] = defaultdict(list)
        for row in checkpoint_rows:
            rows_by_brand[row.normalized_brand].append(row)

        breakdown_by_brand = {
            item.normalized_brand: item
            for item in diagnostics.brand_breakdown
        }

        selected_brands = [normalize_brand(item) for item in self.TARGET_BRANDS]
        if brand_filter:
            selected_brands = [item for item in selected_brands if item in brand_filter]
            for item in sorted(brand_filter):
                if item not in selected_brands:
                    selected_brands.append(item)

        out: list[ArticleVariantCheckpointBrandSummary] = []
        for normalized_brand in selected_brands:
            brand_rows = rows_by_brand.get(normalized_brand, [])
            breakdown = breakdown_by_brand.get(normalized_brand)
            raw_brand = (
                breakdown.raw_brand
                if breakdown is not None
                else (brand_rows[0].raw_brand if brand_rows else normalized_brand)
            )
            supplier_id = (
                breakdown.supplier_id
                if breakdown is not None
                else (brand_rows[0].resolved_supplier_id if brand_rows else None)
            )
            total_pairs = breakdown.total_pairs if breakdown is not None else len(brand_rows)
            linked_before_or_current = breakdown.linked_pairs if breakdown is not None else 0
            variant_would_find_total = (
                breakdown.variant_lookup_would_find_count
                if breakdown is not None
                else sum(1 for row in brand_rows if row.recommendation in self.SAFE_RECOMMENDATIONS)
            )
            counter = Counter(row.status for row in brand_rows)
            summary = ArticleVariantCheckpointBrandSummary(
                raw_brand=raw_brand,
                normalized_brand=normalized_brand,
                resolved_supplier_id=supplier_id,
                total_pairs=total_pairs,
                linked_before_or_current=linked_before_or_current,
                variant_would_find_total=variant_would_find_total,
                already_linked_same_key=counter.get(self.STATUS_ALREADY_LINKED_SAME_KEY, 0),
                already_linked_conflicting_key=counter.get(self.STATUS_ALREADY_LINKED_CONFLICTING_KEY, 0),
                remaining_safe_to_apply=counter.get(self.STATUS_SAFE_TO_APPLY, 0),
                needs_manual_review=counter.get(self.STATUS_NEEDS_MANUAL_REVIEW, 0),
                suspicious=counter.get(self.STATUS_SKIPPED_SUSPICIOUS, 0),
                semantic_conflict=counter.get(self.STATUS_SKIPPED_SEMANTIC_CONFLICT, 0),
                exact_not_found=counter.get(self.STATUS_EXACT_NOT_FOUND, 0),
                skipped_low_confidence=counter.get(self.STATUS_SKIPPED_LOW_CONFIDENCE, 0),
                non_auto_ignore=counter.get(self.STATUS_NON_AUTO_IGNORE, 0),
                recommended_next_action=self._brand_recommended_action(
                    normalized_brand=normalized_brand,
                    counter=counter,
                ),
            )
            out.append(summary)
        return out

    def _brand_recommended_action(self, *, normalized_brand: str, counter: Counter[str]) -> str:
        if normalized_brand == self.POLMO_NORMALIZED:
            return "review_only"
        if counter.get(self.STATUS_SAFE_TO_APPLY, 0) > 0 and counter.get(self.STATUS_SKIPPED_SUSPICIOUS, 0) == 0 and counter.get(
            self.STATUS_SKIPPED_SEMANTIC_CONFLICT,
            0,
        ) == 0 and counter.get(self.STATUS_ALREADY_LINKED_CONFLICTING_KEY, 0) == 0:
            return "ready_for_next_batch"
        if counter.get(self.STATUS_ALREADY_LINKED_SAME_KEY, 0) > 0 and counter.get(self.STATUS_SAFE_TO_APPLY, 0) == 0:
            return "already_applied_or_exhausted"
        if counter.get(self.STATUS_ALREADY_LINKED_CONFLICTING_KEY, 0) > 0 or counter.get(self.STATUS_SKIPPED_SUSPICIOUS, 0) > 0:
            return "manual_review"
        if counter.get(self.STATUS_NEEDS_MANUAL_REVIEW, 0) > 0 or counter.get(self.STATUS_SKIPPED_SEMANTIC_CONFLICT, 0) > 0:
            return "manual_review"
        return "no_safe_batch"

    def _build_recommendation(
        self,
        *,
        supplier_code: str,
        brand_summaries: list[ArticleVariantCheckpointBrandSummary],
    ) -> ArticleVariantCheckpointRecommendation:
        eligible = [
            item
            for item in brand_summaries
            if item.normalized_brand != self.POLMO_NORMALIZED
            and item.remaining_safe_to_apply > 0
            and item.suspicious == 0
            and item.semantic_conflict == 0
            and item.already_linked_conflicting_key == 0
        ]
        if not eligible:
            return ArticleVariantCheckpointRecommendation(
                recommended_next_brand="",
                recommended_limit=0,
                expected_safe_candidates=0,
                command_to_run_next_dry_run="",
                command_to_run_next_real="",
            )

        selected = sorted(
            eligible,
            key=lambda item: (-item.remaining_safe_to_apply, item.raw_brand or ""),
        )[0]
        recommended_limit = min(20, selected.remaining_safe_to_apply)
        dry_run = (
            "python manage.py autodb_apply_article_variant_links "
            f'--supplier {supplier_code.upper()} --brand "{selected.raw_brand}" --only-remaining --limit {recommended_limit} --min-confidence 0.9 --dry-run'
        )
        real = (
            "python manage.py autodb_apply_article_variant_links "
            f'--supplier {supplier_code.upper()} --brand "{selected.raw_brand}" --only-remaining --limit {recommended_limit} --min-confidence 0.9'
        )
        return ArticleVariantCheckpointRecommendation(
            recommended_next_brand=selected.raw_brand,
            recommended_limit=recommended_limit,
            expected_safe_candidates=selected.remaining_safe_to_apply,
            command_to_run_next_dry_run=dry_run,
            command_to_run_next_real=real,
        )

    def _build_polmo_summary(self, *, checkpoint_rows: list[ArticleVariantCheckpointRow]) -> PolmoReviewSummary:
        polmo_rows = [row for row in checkpoint_rows if row.normalized_brand == self.POLMO_NORMALIZED]
        counter = Counter(row.status for row in polmo_rows)
        related_to_known_suspicious = sum(1 for row in polmo_rows if row.related_to_known_suspicious_product)
        exhaust_to_shock_risk = sum(1 for row in polmo_rows if self._is_exhaust_to_shock_risk(row=row))
        examples = tuple(polmo_rows[:20])
        return PolmoReviewSummary(
            safe_to_apply=counter.get(self.STATUS_SAFE_TO_APPLY, 0),
            suspicious=counter.get(self.STATUS_SKIPPED_SUSPICIOUS, 0),
            semantic_conflict=counter.get(self.STATUS_SKIPPED_SEMANTIC_CONFLICT, 0),
            already_linked_same_key=counter.get(self.STATUS_ALREADY_LINKED_SAME_KEY, 0),
            already_linked_conflicting_key=counter.get(self.STATUS_ALREADY_LINKED_CONFLICTING_KEY, 0),
            related_to_known_suspicious_products=related_to_known_suspicious,
            exhaust_to_shock_risk=exhaust_to_shock_risk,
            recommended_next_action="review_only",
            examples=examples,
        )

    def _recommended_action(self, *, normalized_brand: str, status: str) -> str:
        if status == self.STATUS_ALREADY_LINKED_SAME_KEY:
            return "none_already_linked"
        if status == self.STATUS_ALREADY_LINKED_CONFLICTING_KEY:
            return "manual_review_existing_link"
        if status == self.STATUS_SKIPPED_SUSPICIOUS:
            return "do_not_apply_suspicious"
        if status == self.STATUS_SKIPPED_SEMANTIC_CONFLICT:
            return "manual_review_semantic_conflict"
        if status == self.STATUS_SKIPPED_LOW_CONFIDENCE:
            return "keep_outside_safe_batch"
        if status == self.STATUS_EXACT_NOT_FOUND:
            return "no_local_candidate"
        if status == self.STATUS_NEEDS_MANUAL_REVIEW:
            return "manual_review"
        if status == self.STATUS_NON_AUTO_IGNORE:
            return "ignore_non_auto"
        if normalized_brand == self.POLMO_NORMALIZED:
            return "review_only"
        return "candidate_for_next_real_apply"

    def _lookup_autodb_context(
        self,
        *,
        supplier_id: int | None,
        article_number: str,
        fallback_title: str,
        cache: dict[tuple[int | None, str], tuple[str, str]],
    ) -> tuple[str, str]:
        cache_key = (supplier_id, str(article_number or "").strip())
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        title = str(fallback_title or "").strip()
        if not title:
            title = self._resolve_article_title(supplier_id=supplier_id, article_number=article_number)
        category = self._resolve_prd_title(supplier_id=supplier_id, article_number=article_number)
        cache[cache_key] = (title, category)
        return cache[cache_key]

    def _resolve_article_title(self, *, supplier_id: int | None, article_number: str) -> str:
        if supplier_id is None or supplier_id <= 0 or not article_number:
            return ""
        columns = list(self.storage.get_local_columns("articles"))
        if not columns:
            return ""
        supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_col = find_column_name(columns, ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"])
        if not supplier_col or not article_col:
            return ""
        rows = self.storage.fetch_local_rows(
            table="articles",
            filters={supplier_col: supplier_id, article_col: article_number},
            limit=1,
            columns=columns,
        )
        if not rows:
            return ""
        row = rows[0]
        for key in ["normalizeddescription", "NormalizedDescription", "description", "Description", "articleName", "articlename", "name"]:
            value = str(find_value(row, [key]) or "").strip()
            if value:
                return value[:255]
        return ""

    def _resolve_prd_title(self, *, supplier_id: int | None, article_number: str) -> str:
        if supplier_id is None or supplier_id <= 0 or not article_number:
            return ""
        product_ids = self._find_product_ids(table="article_prd", supplier_id=supplier_id, article_number=article_number)
        if not product_ids:
            product_ids = self._find_product_ids(table="article_links", supplier_id=supplier_id, article_number=article_number)
        if not product_ids:
            return ""

        prd_columns = list(self.storage.get_local_columns("prd"))
        if not prd_columns:
            return ""
        id_col = find_column_name(prd_columns, ["id", "productid", "ProductId", "prdid", "prdId"])
        if not id_col:
            return ""
        prd_rows = self.storage.fetch_local_rows_in(
            table="prd",
            column=id_col,
            values=product_ids,
            limit=max(100, len(product_ids) * 2),
            columns=prd_columns,
        )
        for row in prd_rows:
            for key in ["fulldescription", "fullDescription", "normalizeddescription", "NormalizedDescription", "description", "Description"]:
                value = str(find_value(row, [key]) or "").strip()
                if value:
                    return value[:255]
        return ""

    def _find_product_ids(self, *, table: str, supplier_id: int, article_number: str) -> list[int]:
        columns = list(self.storage.get_local_columns(table))
        if not columns:
            return []
        supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_col = find_column_name(columns, ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"])
        if not supplier_col or not article_col:
            return []
        rows = self.storage.fetch_local_rows(
            table=table,
            filters={supplier_col: supplier_id, article_col: article_number},
            limit=500,
            columns=columns,
        )
        product_ids: list[int] = []
        for row in rows:
            prd_id = _safe_int(find_value(row, ["productId", "productid", "ProductId", "prdid", "prdId", "id"]))
            if prd_id is None or prd_id in product_ids:
                continue
            product_ids.append(prd_id)
        return product_ids

    def _has_semantic_conflict(
        self,
        *,
        raw_name: str,
        autodb_title: str,
        autodb_category: str,
        corrected_article: str,
    ) -> bool:
        raw = str(raw_name or "").strip()
        title_blob = " ".join(item for item in [autodb_title, autodb_category] if item).strip()
        corrected = str(corrected_article or "").strip().upper()
        if not raw or not title_blob:
            return False
        if corrected and corrected in raw.upper():
            return False
        raw_tokens = self._normalized_tokens(raw)
        autodb_tokens = self._normalized_tokens(title_blob)
        if not raw_tokens or not autodb_tokens:
            return False
        return raw_tokens.isdisjoint(autodb_tokens)

    def _normalized_tokens(self, text: str) -> set[str]:
        out: set[str] = set()
        for token in self._TOKEN_RE.findall(str(text or "").lower()):
            value = (
                token.replace("і", "и")
                .replace("ї", "и")
                .replace("є", "е")
                .replace("ґ", "г")
            )
            if value and not value.isdigit():
                out.add(value)
        return out

    def _is_exhaust_to_shock_risk(self, *, row: ArticleVariantCheckpointRow) -> bool:
        raw_tokens = self._normalized_tokens(row.raw_product_name)
        autodb_tokens = self._normalized_tokens(" ".join([row.autodb_title, row.autodb_category]))
        return bool(raw_tokens & self._EXHAUST_TOKENS) and bool(autodb_tokens & self._SHOCK_TOKENS)


__all__ = [
    "ArticleVariantCheckpointRow",
    "ArticleVariantCheckpointBrandSummary",
    "ArticleVariantCheckpointRecommendation",
    "ArticleVariantCheckpointReport",
    "AutoDbArticleVariantApplyCheckpointService",
    "PolmoReviewSummary",
]
