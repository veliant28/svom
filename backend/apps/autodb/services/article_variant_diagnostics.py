from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import re
from typing import Any, Iterable

from django.db.models import Q

from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.raw_offer_enrichment import AutoDbRawOfferEnrichmentService, PairBucket, PairResolution
from apps.autodb.services.supplier_brand_matcher import SupplierBrandMatcher
from apps.supplier_imports.gpl_article_resolver import GplArticleResolver
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


@dataclass(frozen=True)
class ArticleVariantDiagnosticsRow:
    supplier: str
    raw_brand: str
    normalized_brand: str
    supplier_id: int | None
    raw_article: str
    normalized_article: str
    raw_product_name: str
    external_sku: str
    article_variants: tuple[str, ...]
    raw_name_alt_tokens: tuple[str, ...]
    raw_name_contains_alt_article: bool
    external_sku_looks_like_manufacturer_article: bool
    matched_product_ids: tuple[str, ...]
    corrected_article_candidate: str
    corrected_article_source: str
    autodb_title: str
    lookup_articles: bool
    lookup_article_numbers: bool
    lookup_article_m: bool
    lookup_article_nn: bool
    lookup_article_oe: bool
    lookup_article_cross: bool
    lookup_article_ean: bool
    recommendation: str
    reason: str
    confidence: float
    sample_offer_id: str


@dataclass(frozen=True)
class BrandVariantDiagnostics:
    raw_brand: str
    normalized_brand: str
    supplier_id: int | None
    total_pairs: int
    linked_pairs: int
    not_found_pairs: int
    top_article_patterns: tuple[str, ...]
    raw_name_alt_article_count: int
    variant_lookup_would_find_count: int
    needs_manual_mapping_count: int


@dataclass(frozen=True)
class RemoteDiagnosticsSummary:
    batch_size: int
    estimated_remote_queries: int
    unresolved_pairs: int
    remote_examples: tuple[tuple[str, str, int | None], ...]
    remote_not_checked_reason: str


@dataclass(frozen=True)
class ArticleVariantDiagnosticsReport:
    supplier: str
    total_raw_offers: int
    total_pairs: int
    linked_pairs: int
    unresolved_pairs: int
    unresolved_supplier_resolved_pairs: int
    diagnostics_rows: tuple[ArticleVariantDiagnosticsRow, ...]
    brand_breakdown: tuple[BrandVariantDiagnostics, ...]
    remote_summary: RemoteDiagnosticsSummary


@dataclass
class _TableLookupIndex:
    table: str
    has_supplier_scope: bool
    normalized_by_supplier: dict[int, set[str]] = field(default_factory=dict)
    normalized_global: set[str] = field(default_factory=set)
    canonical_by_key: dict[tuple[int | None, str], str] = field(default_factory=dict)


class AutoDbArticleVariantDiagnosticsService:
    ARTICLE_COLUMNS = [
        "DataSupplierArticleNumber",
        "datasupplierarticlenumber",
        "PartsDataSupplierArticleNumber",
        "articlenumber",
        "article",
        "number",
        "ean",
        "oe",
        "cross",
        "reference",
    ]
    SUPPLIER_COLUMNS = ["supplierId", "supplierid", "SupplierId", "supplier_id", "supplier"]
    LOOKUP_TABLES = ("articles", "article_numbers", "article_m", "article_nn", "article_oe", "article_cross", "article_ean")
    NON_AUTO_HINTS = {
        "БЕЗБРЕНДУ",
        "ТМК",
        "ПРОМБИЗНЕС",
        "ПОКРАСКО",
        "CSSYSTEM",
        "MRBUILD",
        "NOVOABRASIVE",
        "VIRA",
        "K2",
    }

    _TOKEN_RE = re.compile(r"\b[A-Z0-9]+(?:[\-\./][A-Z0-9]+)+\b|\b[A-Z]{1,6}[0-9]{2,}[A-Z0-9\-\./]*\b")
    _ARTICLE_LIKE_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9\-\./]{4,}$")

    def __init__(
        self,
        *,
        storage: AutoDbRawCloneStorage | None = None,
        enrichment_service: AutoDbRawOfferEnrichmentService | None = None,
        article_normalizer: ArticleNumberNormalizer | None = None,
        brand_matcher: SupplierBrandMatcher | None = None,
    ):
        self.storage = storage or AutoDbRawCloneStorage()
        self.enrichment_service = enrichment_service or AutoDbRawOfferEnrichmentService(storage=self.storage)
        self.article_normalizer = article_normalizer or ArticleNumberNormalizer()
        self.brand_matcher = brand_matcher or SupplierBrandMatcher(storage=self.storage)
        self.gpl_article_resolver = GplArticleResolver()

    def diagnose(
        self,
        *,
        supplier_code: str,
        limit: int,
        brand_filter: set[str] | None = None,
        batch_size: int = 1000,
    ) -> ArticleVariantDiagnosticsReport:
        offers = list(self._build_queryset(supplier_code=supplier_code, limit=limit, brand_filter=brand_filter))
        buckets, _, failed_build = self.enrichment_service.build_pair_buckets(offers=offers)

        resolutions: list[PairResolution] = []
        unresolved_by_chunk: list[int] = []
        chunk_size = max(int(batch_size), 1)
        for start in range(0, len(buckets), chunk_size):
            chunk = buckets[start : start + chunk_size]
            local = self.enrichment_service._resolve_local_chunk(chunk)
            unresolved_by_chunk.append(sum(1 for item in local if not item.article_key))
            resolutions.extend(local)

        pair_sample = self._pair_samples(offers)
        unresolved_rows = [item for item in resolutions if not item.article_key and item.supplier_id is not None]

        row_builders = [self._build_row_context(item=item, pair_sample=pair_sample, supplier_code=supplier_code) for item in unresolved_rows]
        value_pool = sorted({value for ctx in row_builders for value in ctx["lookup_values"] if value})

        table_indexes = {
            table: self._build_lookup_index(table=table, query_values=value_pool)
            for table in self.LOOKUP_TABLES
        }

        diagnostics_rows: list[ArticleVariantDiagnosticsRow] = []
        for ctx in row_builders:
            diagnostics_rows.append(self._evaluate_row(ctx=ctx, table_indexes=table_indexes, supplier_code=supplier_code))

        linked_pairs = sum(1 for item in resolutions if item.article_key)
        unresolved_pairs = len(resolutions) - linked_pairs
        remote_examples = tuple(
            (
                item.bucket.sample_brand,
                item.bucket.sample_article,
                item.supplier_id,
            )
            for item in unresolved_rows[:20]
        )

        brand_breakdown = self._build_brand_breakdown(
            supplier_code=supplier_code,
            buckets=buckets,
            resolutions=resolutions,
            diagnostics_rows=diagnostics_rows,
        )

        return ArticleVariantDiagnosticsReport(
            supplier=supplier_code.lower(),
            total_raw_offers=len(offers),
            total_pairs=len(buckets),
            linked_pairs=linked_pairs,
            unresolved_pairs=unresolved_pairs + failed_build,
            unresolved_supplier_resolved_pairs=len(unresolved_rows),
            diagnostics_rows=tuple(diagnostics_rows),
            brand_breakdown=tuple(brand_breakdown),
            remote_summary=RemoteDiagnosticsSummary(
                batch_size=chunk_size,
                estimated_remote_queries=sum(1 for unresolved_count in unresolved_by_chunk if unresolved_count > 0),
                unresolved_pairs=len(unresolved_rows),
                remote_examples=remote_examples,
                remote_not_checked_reason="local_diagnostics_only",
            ),
        )

    def generate_lookup_variants(self, *, brand: str, article: str) -> tuple[str, ...]:
        normalized_brand = normalize_brand(brand)
        base = self.article_normalizer.normalize(article).search_variants
        out: list[str] = []

        def add(value: str) -> None:
            cleaned = str(value or "").strip().upper()
            if cleaned and cleaned not in out:
                out.append(cleaned)

        for item in base:
            add(item)
        if article:
            add(article)
            add(article.replace(" ", ""))
            add(article.replace("-", ""))
            add(article.replace("/", ""))
            add(article.replace(".", ""))
            add(article.replace("/", "-").replace(" ", ""))
            add(article.replace("-", " "))

        compact = normalize_article(article)
        if compact:
            add(compact)

        if normalized_brand in {"WIXFILTERS", "FRAM", "MANNFILTER", "NGK", "ERT", "WOKING"} and compact:
            if re.match(r"^[A-Z]{1,4}\d+[A-Z0-9]*$", compact):
                prefix = re.match(r"^[A-Z]+", compact)
                if prefix:
                    head = prefix.group(0)
                    tail = compact[len(head) :]
                    add(f"{head} {tail}")
                    add(f"{head}-{tail}")
            if "." in article:
                add(article.replace(".", ""))
                add(article.replace(".", "-"))
            if "/" in article:
                add(article.replace("/", ""))
                add(article.replace("/", "-"))

        return tuple(out)

    def extract_article_like_tokens(self, text: str) -> tuple[str, ...]:
        source = str(text or "").upper()
        tokens: list[str] = []
        for match in self._TOKEN_RE.findall(source):
            token = str(match or "").strip().strip("()[]{}<>\"")
            if not token:
                continue
            if not self.looks_like_manufacturer_article(token):
                continue
            if token not in tokens:
                tokens.append(token)
        return tuple(tokens[:20])

    def looks_like_manufacturer_article(self, value: str) -> bool:
        token = str(value or "").strip().upper()
        if not token:
            return False
        if token.isdigit():
            return False
        return bool(self._ARTICLE_LIKE_RE.match(token))

    def recommend_from_signals(
        self,
        *,
        supplier_code: str,
        raw_brand: str,
        core_hit_raw_name: bool,
        core_hit_external: bool,
        core_hit_variant: bool,
        old_new_hit: bool,
        any_reference_hit: bool,
        external_sku_looks_like_article: bool,
        raw_name_confirms_external: bool,
        candidate_count: int,
    ) -> tuple[str, str, float]:
        if normalize_brand(raw_brand) in self.NON_AUTO_HINTS:
            return ("non_auto_ignore", "supplier_only_or_non_auto_brand", 0.10)

        if core_hit_raw_name and candidate_count == 1:
            return ("article_in_raw_name", "article_in_raw_name_high_confidence", 0.95)

        if core_hit_external:
            if supplier_code.lower() == "gpl" and not raw_name_confirms_external:
                return ("needs_manual_mapping", "external_sku_unverified_for_gpl", 0.55)
            if external_sku_looks_like_article:
                return ("try_external_sku", "external_sku_matches_supplier_article", 0.91)
            return ("needs_manual_mapping", "external_sku_match_needs_context", 0.70)

        if core_hit_variant and candidate_count == 1:
            return ("try_variant", "variant_matches_supplier_article", 0.90)

        if old_new_hit:
            return ("old_new_number_candidate", "article_m_or_article_nn_candidate", 0.85)

        if any_reference_hit:
            return ("needs_manual_mapping", "reference_table_match_needs_review", 0.65)

        return ("exact_not_found", "no_local_match_in_variant_or_reference_tables", 0.0)

    def _build_queryset(self, *, supplier_code: str, limit: int, brand_filter: set[str] | None):
        code = str(supplier_code or "").strip().lower()
        qs = (
            SupplierRawOffer.objects.select_related("source", "supplier", "matched_product")
            .filter(Q(source__code__iexact=code) | Q(supplier__code__iexact=code))
            .order_by("id")
        )
        if limit > 0:
            qs = qs[:limit]
        offers = list(qs)
        if not brand_filter:
            return offers
        return [item for item in offers if normalize_brand(item.brand_name or item.normalized_brand) in brand_filter]

    def _pair_samples(self, offers: Iterable[SupplierRawOffer]) -> dict[tuple[str, str], SupplierRawOffer]:
        sample: dict[tuple[str, str], SupplierRawOffer] = {}
        for offer in offers:
            normalized_brand = str(offer.normalized_brand or "").strip() or normalize_brand(offer.brand_name)
            article_raw = str(offer.article or "").strip() or str(offer.external_sku or "").strip()
            source_code = str(getattr(getattr(offer, "source", None), "code", "") or "").strip().lower()
            supplier_code = str(getattr(getattr(offer, "supplier", None), "code", "") or "").strip().lower()
            if source_code == "gpl" or supplier_code == "gpl":
                resolved = self.gpl_article_resolver.resolve(
                    raw_payload=offer.raw_payload if isinstance(offer.raw_payload, dict) else {},
                    article=str(offer.article or ""),
                    external_sku=str(offer.external_sku or ""),
                )
                if resolved.manufacturer_article:
                    article_raw = resolved.manufacturer_article
            normalized_article = str(offer.normalized_article or "").strip() or normalize_article(article_raw)
            key = (normalized_brand, normalized_article)
            if key not in sample:
                sample[key] = offer
        return sample

    def _build_row_context(self, *, item: PairResolution, pair_sample: dict[tuple[str, str], SupplierRawOffer], supplier_code: str) -> dict[str, Any]:
        sample = pair_sample.get((item.bucket.normalized_brand, item.bucket.normalized_article))
        sample_brand = str(sample.brand_name if sample else item.bucket.sample_brand or "")
        sample_article = str(sample.article if sample else item.bucket.sample_article or "")
        sample_name = str(sample.product_name if sample else "")
        sample_external = str(sample.external_sku if sample else "")
        offer_id = str(sample.id) if sample else ""

        variants = self.generate_lookup_variants(brand=item.bucket.normalized_brand, article=item.bucket.sample_article or item.bucket.normalized_article)
        base_norms = {normalize_article(v) for v in variants if v}
        raw_tokens = self.extract_article_like_tokens(sample_name)
        alt_tokens = tuple(token for token in raw_tokens if normalize_article(token) not in base_norms)

        lookup_values = list(variants)
        lookup_values.extend(alt_tokens)
        if sample_external:
            lookup_values.append(sample_external)

        norm_origin: dict[str, set[str]] = defaultdict(set)
        raw_map: dict[str, str] = {}
        for token in variants:
            norm = normalize_article(token)
            if not norm:
                continue
            norm_origin[norm].add("variant")
            raw_map.setdefault(norm, token)
        for token in alt_tokens:
            norm = normalize_article(token)
            if not norm:
                continue
            norm_origin[norm].add("raw_name")
            raw_map.setdefault(norm, token)
        if sample_external:
            norm = normalize_article(sample_external)
            if norm:
                norm_origin[norm].add("external_sku")
                raw_map.setdefault(norm, sample_external)

        matched_product_ids = tuple(sorted(str(pid) for pid in item.bucket.matched_product_ids if pid))

        return {
            "item": item,
            "sample_brand": sample_brand,
            "sample_article": sample_article,
            "sample_name": sample_name,
            "sample_external": sample_external,
            "offer_id": offer_id,
            "variants": tuple(variants),
            "alt_tokens": alt_tokens,
            "lookup_values": tuple(sorted({str(v).strip().upper() for v in lookup_values if str(v).strip()})),
            "norm_origin": norm_origin,
            "norm_raw_map": raw_map,
            "matched_product_ids": matched_product_ids,
            "supplier_code": supplier_code,
        }

    def _build_lookup_index(self, *, table: str, query_values: list[str]) -> _TableLookupIndex:
        columns = self.storage.get_local_columns(table)
        if not columns:
            return _TableLookupIndex(table=table, has_supplier_scope=False)

        article_column = self.storage.first_existing_column(table=table, candidates=self.ARTICLE_COLUMNS)
        supplier_column = self.storage.first_existing_column(table=table, candidates=self.SUPPLIER_COLUMNS)
        if not article_column:
            return _TableLookupIndex(table=table, has_supplier_scope=bool(supplier_column))

        index = _TableLookupIndex(table=table, has_supplier_scope=bool(supplier_column))
        for chunk_start in range(0, len(query_values), 200):
            chunk = query_values[chunk_start : chunk_start + 200]
            rows = self.storage.fetch_local_rows_in(
                table=table,
                column=article_column,
                values=chunk,
                limit=max(len(chunk) * 200, 2000),
                columns=[item for item in [article_column, supplier_column] if item],
            )
            for row in rows:
                value = str(row.get(article_column) or "").strip()
                normalized = normalize_article(value)
                if not normalized:
                    continue
                supplier_id = self._to_int(row.get(supplier_column)) if supplier_column else None
                if supplier_id is None:
                    index.normalized_global.add(normalized)
                    index.canonical_by_key.setdefault((None, normalized), value)
                    continue
                index.normalized_by_supplier.setdefault(supplier_id, set()).add(normalized)
                index.canonical_by_key.setdefault((supplier_id, normalized), value)
        return index

    def _evaluate_row(self, *, ctx: dict[str, Any], table_indexes: dict[str, _TableLookupIndex], supplier_code: str) -> ArticleVariantDiagnosticsRow:
        item: PairResolution = ctx["item"]
        supplier_id = item.supplier_id
        candidate_norms = set(ctx["norm_origin"].keys())

        table_hits: dict[str, set[str]] = {}
        for table, index in table_indexes.items():
            hits = self._table_hits(index=index, supplier_id=supplier_id, candidate_norms=candidate_norms)
            table_hits[table] = hits

        core_hits = set(table_hits.get("articles", set())) | set(table_hits.get("article_numbers", set()))
        raw_name_hits = {norm for norm in core_hits if "raw_name" in ctx["norm_origin"].get(norm, set())}
        external_hits = {norm for norm in core_hits if "external_sku" in ctx["norm_origin"].get(norm, set())}
        variant_hits = {norm for norm in core_hits if "variant" in ctx["norm_origin"].get(norm, set())}

        old_new_hits = set(table_hits.get("article_m", set())) | set(table_hits.get("article_nn", set()))
        reference_hits = set(table_hits.get("article_oe", set())) | set(table_hits.get("article_cross", set())) | set(table_hits.get("article_ean", set()))

        raw_name_confirms_external = any(
            normalize_article(ctx["sample_external"]) == norm and "raw_name" in ctx["norm_origin"].get(norm, set())
            for norm in external_hits
        )

        recommendation, reason, confidence = self.recommend_from_signals(
            supplier_code=supplier_code,
            raw_brand=ctx["sample_brand"],
            core_hit_raw_name=bool(raw_name_hits),
            core_hit_external=bool(external_hits),
            core_hit_variant=bool(variant_hits),
            old_new_hit=bool(old_new_hits and not core_hits),
            any_reference_hit=bool(reference_hits),
            external_sku_looks_like_article=self.looks_like_manufacturer_article(ctx["sample_external"]),
            raw_name_confirms_external=raw_name_confirms_external,
            candidate_count=len(core_hits | old_new_hits),
        )

        corrected_norm = ""
        corrected_source = ""
        if raw_name_hits:
            corrected_norm = sorted(raw_name_hits)[0]
            corrected_source = "raw_name"
        elif external_hits:
            corrected_norm = sorted(external_hits)[0]
            corrected_source = "external_sku"
        elif variant_hits:
            corrected_norm = sorted(variant_hits)[0]
            corrected_source = "variant"
        elif old_new_hits:
            corrected_norm = sorted(old_new_hits)[0]
            corrected_source = "article_m_or_nn"

        corrected_value = ""
        if corrected_norm:
            for table in ("article_numbers", "articles", "article_m", "article_nn"):
                lookup_index = table_indexes.get(table)
                if not lookup_index:
                    continue
                key = (supplier_id, corrected_norm)
                corrected_value = lookup_index.canonical_by_key.get(key) or lookup_index.canonical_by_key.get((None, corrected_norm), "")
                if corrected_value:
                    break
            if not corrected_value:
                corrected_value = ctx["norm_raw_map"].get(corrected_norm, corrected_norm)

        autodb_title = ""
        if corrected_norm:
            autodb_title = self._lookup_autodb_title(
                supplier_id=supplier_id,
                article_norm=corrected_norm,
                candidate_raw=corrected_value,
            )

        return ArticleVariantDiagnosticsRow(
            supplier=supplier_code.lower(),
            raw_brand=ctx["sample_brand"],
            normalized_brand=item.bucket.normalized_brand,
            supplier_id=supplier_id,
            raw_article=ctx["sample_article"],
            normalized_article=item.bucket.normalized_article,
            raw_product_name=ctx["sample_name"],
            external_sku=ctx["sample_external"],
            article_variants=ctx["variants"],
            raw_name_alt_tokens=ctx["alt_tokens"],
            raw_name_contains_alt_article=bool(ctx["alt_tokens"]),
            external_sku_looks_like_manufacturer_article=self.looks_like_manufacturer_article(ctx["sample_external"]),
            matched_product_ids=ctx["matched_product_ids"],
            corrected_article_candidate=corrected_value,
            corrected_article_source=corrected_source,
            autodb_title=autodb_title,
            lookup_articles=bool(table_hits.get("articles")),
            lookup_article_numbers=bool(table_hits.get("article_numbers")),
            lookup_article_m=bool(table_hits.get("article_m")),
            lookup_article_nn=bool(table_hits.get("article_nn")),
            lookup_article_oe=bool(table_hits.get("article_oe")),
            lookup_article_cross=bool(table_hits.get("article_cross")),
            lookup_article_ean=bool(table_hits.get("article_ean")),
            recommendation=recommendation,
            reason=reason,
            confidence=confidence,
            sample_offer_id=ctx["offer_id"],
        )

    def _lookup_autodb_title(self, *, supplier_id: int | None, article_norm: str, candidate_raw: str) -> str:
        if supplier_id is None:
            return ""
        table = "articles"
        columns = self.storage.get_local_columns(table)
        if not columns:
            return ""
        article_col = self.storage.first_existing_column(table=table, candidates=self.ARTICLE_COLUMNS)
        supplier_col = self.storage.first_existing_column(table=table, candidates=self.SUPPLIER_COLUMNS)
        if not article_col:
            return ""
        title_col = self.storage.first_existing_column(
            table=table,
            candidates=["articleName", "articlename", "name", "description", "designation"],
        )
        if not title_col:
            return ""

        values = [item for item in {candidate_raw, article_norm} if str(item or "").strip()]
        if not values:
            return ""

        rows = self.storage.fetch_local_rows_in(
            table=table,
            column=article_col,
            values=values,
            extra_filters={supplier_col: supplier_id} if supplier_col else None,
            limit=20,
            columns=[article_col, title_col, supplier_col] if supplier_col else [article_col, title_col],
        )
        for row in rows:
            candidate_article = normalize_article(str(row.get(article_col) or ""))
            if candidate_article != article_norm:
                continue
            title = str(row.get(title_col) or "").strip()
            if title:
                return title
        return ""

    def _table_hits(self, *, index: _TableLookupIndex, supplier_id: int | None, candidate_norms: set[str]) -> set[str]:
        if not candidate_norms:
            return set()
        hits: set[str] = set()
        if index.has_supplier_scope and supplier_id is not None:
            supplier_values = index.normalized_by_supplier.get(int(supplier_id), set())
            hits.update(candidate_norms.intersection(supplier_values))
        hits.update(candidate_norms.intersection(index.normalized_global))
        return hits

    def _build_brand_breakdown(
        self,
        *,
        supplier_code: str,
        buckets: list[PairBucket],
        resolutions: list[PairResolution],
        diagnostics_rows: list[ArticleVariantDiagnosticsRow],
    ) -> list[BrandVariantDiagnostics]:
        target_brands = [
            "WIX FILTERS",
            "SPIDAN",
            "AUTOMEGA",
            "POLMO",
            "ERT",
            "FRAM",
            "WOKING",
            "AL-KO",
            "FENOX",
            "BOSAL",
        ]
        target_norm = {normalize_brand(item): item for item in target_brands}

        brand_match = self.brand_matcher.resolve_many(list(target_norm.keys()))
        buckets_by_brand: defaultdict[str, list[PairBucket]] = defaultdict(list)
        for bucket in buckets:
            buckets_by_brand[bucket.normalized_brand].append(bucket)

        linked_counter: Counter[str] = Counter()
        unresolved_counter: Counter[str] = Counter()
        for row in resolutions:
            key = row.bucket.normalized_brand
            if row.article_key:
                linked_counter[key] += 1
            else:
                unresolved_counter[key] += 1

        row_by_brand: defaultdict[str, list[ArticleVariantDiagnosticsRow]] = defaultdict(list)
        for row in diagnostics_rows:
            row_by_brand[row.normalized_brand].append(row)

        out: list[BrandVariantDiagnostics] = []
        for norm_key, raw_brand in target_norm.items():
            brand_rows = row_by_brand.get(norm_key, [])
            pattern_counter = Counter(self._article_pattern(item.raw_article) for item in brand_rows if item.raw_article)
            top_patterns = tuple([name for name, _ in pattern_counter.most_common(5)])

            out.append(
                BrandVariantDiagnostics(
                    raw_brand=raw_brand,
                    normalized_brand=norm_key,
                    supplier_id=(brand_match.get(norm_key).matched_supplier_id if brand_match.get(norm_key) else None),
                    total_pairs=len(buckets_by_brand.get(norm_key, [])),
                    linked_pairs=linked_counter.get(norm_key, 0),
                    not_found_pairs=unresolved_counter.get(norm_key, 0),
                    top_article_patterns=top_patterns,
                    raw_name_alt_article_count=sum(1 for item in brand_rows if item.raw_name_contains_alt_article),
                    variant_lookup_would_find_count=sum(
                        1
                        for item in brand_rows
                        if item.recommendation in {"article_in_raw_name", "try_variant", "try_external_sku", "old_new_number_candidate"}
                    ),
                    needs_manual_mapping_count=sum(1 for item in brand_rows if item.recommendation == "needs_manual_mapping"),
                )
            )
        return out

    def _article_pattern(self, value: str) -> str:
        text = str(value or "").strip().upper()
        if not text:
            return "empty"
        normalized = normalize_article(text)
        if normalized.isdigit():
            return "numeric_only"
        parts: list[str] = []
        if "/" in text:
            parts.append("slash")
        if "-" in text:
            parts.append("hyphen")
        if "." in text:
            parts.append("dot")
        if re.search(r"[A-Z]", text) and re.search(r"\d", text):
            parts.append("alnum_mix")
        if not parts:
            parts.append("other")
        return "+".join(parts)

    def _to_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


__all__ = [
    "ArticleVariantDiagnosticsRow",
    "BrandVariantDiagnostics",
    "RemoteDiagnosticsSummary",
    "ArticleVariantDiagnosticsReport",
    "AutoDbArticleVariantDiagnosticsService",
]
