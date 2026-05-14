from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Iterable

from django.db import transaction

from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.article_enrichment import AutoDbArticleEnrichmentService
from apps.autodb.services.article_lookup import ArticleLookupResult
from apps.autodb.services.column_helpers import find_value
from apps.autodb.services.product_linker import AutoDbProductLinkService
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.supplier_brand_matcher import SupplierBrandCandidate, SupplierBrandMatcher
from apps.catalog.models import Product
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


@dataclass
class PairBucket:
    normalized_brand: str
    normalized_article: str
    sample_brand: str
    sample_article: str
    article_variants: tuple[str, ...] = ()
    source_id: str | None = None
    supplier_id: str | None = None
    offer_count: int = 0
    matched_product_ids: set[str] = field(default_factory=set)


@dataclass
class PairResolution:
    bucket: PairBucket
    supplier_id: int | None = None
    canonical_article_number: str = ""
    article_key: str = ""
    article_id: int | None = None
    source: str = "not_found"  # local|remote|not_found|no_remote
    reason: str = ""
    supplier_candidates: tuple[SupplierBrandCandidate, ...] = ()
    warnings: list[str] = field(default_factory=list)


@dataclass
class RawOfferEnrichmentSummary:
    total_raw_offers: int = 0
    unique_pairs: int = 0
    local_hits: int = 0
    remote_hits: int = 0
    not_found: int = 0
    failed: int = 0
    enriched_articles: int = 0
    linked_products: int = 0
    skipped_no_matched_product: int = 0
    skipped_disabled_no_remote: int = 0
    remote_enabled: bool = False
    remote_attempted: bool = False
    remote_queries: int = 0
    remote_errors: int = 0
    remote_disabled_reason: str = ""
    elapsed_seconds: float = 0.0


class AutoDbRawOfferEnrichmentService:
    SUPPLIER_LOOKUP_COLUMNS = ("matchcode", "description", "fulldescription")
    ARTICLE_NUMBER_COLUMNS = ("DataSupplierArticleNumber", "datasupplierarticlenumber", "articlenumber", "article", "number")
    ARTICLE_SUPPLIER_COLUMNS = ("supplierId", "supplierid", "SupplierId", "supplier_id", "supplier")
    RELATED_TABLES: tuple[str, ...] = (
        "article_attributes",
        "article_li",
        "article_links",
        "article_prd",
        "article_numbers",
        "article_images",
        "article_inf",
        "article_oe",
        "article_cross",
        "article_ean",
        "article_nn",
        "article_m",
        "article_acc",
        "article_parts",
    )

    def __init__(
        self,
        *,
        storage: AutoDbRawCloneStorage | None = None,
        enrichment_service: AutoDbArticleEnrichmentService | None = None,
        product_linker: AutoDbProductLinkService | None = None,
        article_normalizer: ArticleNumberNormalizer | None = None,
        brand_matcher: SupplierBrandMatcher | None = None,
    ):
        self.storage = storage or AutoDbRawCloneStorage()
        self.enrichment_service = enrichment_service or AutoDbArticleEnrichmentService(storage=self.storage)
        self.product_linker = product_linker or AutoDbProductLinkService()
        self.article_normalizer = article_normalizer or ArticleNumberNormalizer()
        self.brand_matcher = brand_matcher or SupplierBrandMatcher(storage=self.storage)

    def build_pair_buckets(self, *, offers: Iterable[SupplierRawOffer]) -> tuple[list[PairBucket], int, int]:
        buckets: dict[tuple[str, str], PairBucket] = {}
        total_raw_offers = 0
        failed = 0

        for offer in offers:
            total_raw_offers += 1
            matched_product = getattr(offer, "matched_product", None)
            if matched_product is None:
                failed += 1
                continue

            article_raw = str(getattr(matched_product, "article", "") or "").strip()
            if not article_raw:
                failed += 1
                continue

            brand_name = str(getattr(getattr(matched_product, "brand", None), "name", "") or "").strip() or str(offer.brand_name or "").strip()
            normalized_brand = str(getattr(matched_product, "normalized_brand", "") or "").strip() or normalize_brand(brand_name)
            normalized_article = normalize_article(article_raw)
            article_normalized = self.article_normalizer.normalize(article_raw or normalized_article)
            if not normalized_brand or not normalized_article:
                failed += 1
                continue

            key = (normalized_brand, normalized_article)
            bucket = buckets.get(key)
            if bucket is None:
                bucket = PairBucket(
                    normalized_brand=normalized_brand,
                    normalized_article=normalized_article,
                    sample_brand=brand_name or normalized_brand,
                    sample_article=article_raw or normalized_article,
                    article_variants=article_normalized.search_variants or (normalized_article,),
                    source_id=str(offer.source_id) if getattr(offer, "source_id", None) else None,
                    supplier_id=str(offer.supplier_id) if getattr(offer, "supplier_id", None) else None,
                )
                buckets[key] = bucket

            bucket.offer_count += 1
            if offer.matched_product_id:
                bucket.matched_product_ids.add(str(offer.matched_product_id))

        return list(buckets.values()), total_raw_offers, failed

    def run(
        self,
        *,
        offers: Iterable[SupplierRawOffer],
        dry_run: bool,
        allow_remote: bool,
        remote_disabled_reason: str = "",
        enrich_related: bool,
        batch_size: int,
        progress_every: int,
        progress_callback,
        remote_error_threshold: int = 3,
    ) -> RawOfferEnrichmentSummary:
        started = time.monotonic()
        summary = RawOfferEnrichmentSummary()

        buckets, total_raw_offers, failed = self.build_pair_buckets(offers=offers)
        summary.total_raw_offers = total_raw_offers
        summary.failed += failed
        summary.unique_pairs = len(buckets)

        resolutions: list[PairResolution] = []
        remote_enabled = allow_remote
        summary.remote_enabled = allow_remote
        summary.remote_disabled_reason = str(remote_disabled_reason or "").strip()
        remote_failures = 0
        processed_pairs = 0
        next_progress = progress_every if progress_every > 0 else 0

        all_product_ids: set[str] = set()
        for bucket in buckets:
            all_product_ids.update(bucket.matched_product_ids)
        product_map = {str(key): value for key, value in Product.objects.in_bulk(all_product_ids).items()} if all_product_ids else {}
        product_updates: dict[str, Product] = {}

        for pair_chunk in self._chunked(buckets, max(batch_size, 1)):
            chunk_resolutions = self._resolve_local_chunk(pair_chunk)
            unresolved = [item for item in chunk_resolutions if not item.article_key]

            if unresolved and remote_enabled:
                summary.remote_attempted = True
                summary.remote_queries += 1
                try:
                    chunk_resolutions = self._resolve_remote_chunk(chunk_resolutions, persist_clone=not dry_run)
                    remote_failures = 0
                except Exception as exc:  # noqa: BLE001
                    remote_failures += 1
                    summary.remote_errors += 1
                    for item in unresolved:
                        item.source = "no_remote"
                        item.warnings.append(f"remote_error:{exc}")
                    if remote_failures >= remote_error_threshold:
                        remote_enabled = False
                        if not summary.remote_disabled_reason:
                            summary.remote_disabled_reason = "remote_error_threshold_reached"

            if unresolved and not remote_enabled:
                for item in chunk_resolutions:
                    if not item.article_key and item.source == "not_found":
                        item.source = "no_remote"

            if enrich_related and not dry_run:
                enriched = self._bulk_related_enrichment(chunk_resolutions, persist_clone=True)
                summary.enriched_articles += enriched

            linked_in_chunk = self._prepare_product_updates(
                resolutions=chunk_resolutions,
                product_map=product_map,
                product_updates=product_updates,
                summary=summary,
            )
            summary.linked_products += linked_in_chunk

            for item in chunk_resolutions:
                if item.article_key:
                    if item.source == "remote":
                        summary.remote_hits += 1
                    else:
                        summary.local_hits += 1
                else:
                    if item.source == "no_remote":
                        summary.skipped_disabled_no_remote += 1
                    else:
                        summary.not_found += 1
                if not item.bucket.matched_product_ids:
                    summary.skipped_no_matched_product += item.bucket.offer_count

            resolutions.extend(chunk_resolutions)
            processed_pairs += len(chunk_resolutions)
            if progress_every > 0 and progress_callback:
                if next_progress > 0 and processed_pairs >= next_progress:
                    elapsed = max(time.monotonic() - started, 0.001)
                    rate = processed_pairs / elapsed
                    remaining = max(summary.unique_pairs - processed_pairs, 0)
                    eta = remaining / rate if rate > 0 else 0.0
                    progress_callback(
                        processed_pairs=processed_pairs,
                        total_pairs=summary.unique_pairs,
                        local_hits=summary.local_hits,
                        remote_hits=summary.remote_hits,
                        missing=summary.not_found + summary.skipped_disabled_no_remote,
                        enriched=summary.enriched_articles,
                        linked=summary.linked_products,
                        elapsed_seconds=elapsed,
                        rate=rate,
                        eta_seconds=eta,
                    )
                    while next_progress > 0 and processed_pairs >= next_progress:
                        next_progress += progress_every

        if not dry_run and product_updates:
            self._bulk_save_products(list(product_updates.values()))

        summary.elapsed_seconds = max(time.monotonic() - started, 0.0)
        return summary

    def _resolve_local_chunk(self, buckets: list[PairBucket]) -> list[PairResolution]:
        source_id = self._single_scope([item.source_id for item in buckets])
        supplier_scope_id = self._single_scope([item.supplier_id for item in buckets])
        brand_results = self.brand_matcher.resolve_many(
            [item.normalized_brand for item in buckets],
            source_id=source_id,
            supplier_id=supplier_scope_id,
        )
        resolutions: list[PairResolution] = []
        for item in buckets:
            matched = brand_results.get(item.normalized_brand)
            resolutions.append(
                PairResolution(
                    bucket=item,
                    supplier_id=matched.matched_supplier_id if matched else None,
                    reason=matched.reason if matched else "brand_not_found",
                    supplier_candidates=matched.candidates if matched else (),
                )
            )

        local_articles = self._bulk_lookup_local_articles(resolutions)
        for item in resolutions:
            if item.supplier_id is None:
                item.reason = item.reason or "brand_not_found"
                continue
            key = (item.supplier_id, item.bucket.normalized_article)
            row = local_articles.get(key)
            if row is None:
                item.reason = "article_not_found_for_supplier"
                continue
            item.article_id = self._to_int(find_value(row, ["articleid", "id"]))
            item.canonical_article_number = self._extract_article_number(row)
            item.article_key = self._compose_article_key(item.supplier_id, item.canonical_article_number)
            if item.article_key:
                item.source = "local"
                item.reason = "matched_local"
        return resolutions

    def _resolve_remote_chunk(self, resolutions: list[PairResolution], *, persist_clone: bool) -> list[PairResolution]:
        unresolved = [item for item in resolutions if not item.article_key]
        if not unresolved:
            return resolutions

        remote_suppliers = self._bulk_lookup_remote_suppliers(
            [item.bucket.normalized_brand for item in unresolved],
            persist_clone=persist_clone,
        )
        for item in unresolved:
            if item.supplier_id is None:
                supplier_id = remote_suppliers.get(item.bucket.normalized_brand)
                if supplier_id is not None:
                    item.supplier_id = supplier_id
                else:
                    item.reason = "brand_not_found"

        remote_articles = self._bulk_lookup_remote_articles(resolutions, persist_clone=persist_clone)
        for item in resolutions:
            if item.article_key:
                continue
            key = (item.supplier_id, item.bucket.normalized_article)
            row = remote_articles.get(key)
            if row is None:
                item.reason = "article_not_found_for_supplier"
                continue
            item.article_id = self._to_int(find_value(row, ["articleid", "id"]))
            item.canonical_article_number = self._extract_article_number(row)
            item.article_key = self._compose_article_key(item.supplier_id, item.canonical_article_number)
            if item.article_key:
                item.source = "remote"
                item.reason = "matched_remote"
        return resolutions

    def _bulk_lookup_local_suppliers(self, brands: list[str]) -> dict[str, int]:
        values = sorted({str(item or "").strip() for item in brands if str(item or "").strip()})
        if not values:
            return {}

        matched_rows: list[dict[str, Any]] = []
        columns = self.storage.get_local_columns("suppliers")
        lookup_columns = [
            name
            for name in self.SUPPLIER_LOOKUP_COLUMNS
            if self.storage.first_existing_column(table="suppliers", candidates=[name])
        ]
        if not lookup_columns:
            return {}

        for lookup_column in lookup_columns:
            for chunk in self._chunked(values, 200):
                matched_rows.extend(
                    self.storage.fetch_local_rows_in(
                        table="suppliers",
                        column=lookup_column,
                        values=list(chunk),
                        limit=max(len(chunk) * 20, 1000),
                        columns=list(columns),
                    )
                )

        result: dict[str, int] = {}
        for row in matched_rows:
            supplier_id = self._to_int(find_value(row, ["id"]))
            if supplier_id is None:
                continue
            for raw_value in [
                find_value(row, ["matchcode"]),
                find_value(row, ["description"]),
                find_value(row, ["fulldescription"]),
            ]:
                normalized = normalize_brand(str(raw_value or ""))
                if normalized and normalized in values and normalized not in result:
                    result[normalized] = supplier_id
        return result

    def _bulk_lookup_remote_suppliers(self, brands: list[str], *, persist_clone: bool) -> dict[str, int]:
        values = sorted({str(item or "").strip() for item in brands if str(item or "").strip()})
        if not values:
            return {}

        matched_rows: list[dict[str, Any]] = []
        columns = self.storage.get_remote_columns("suppliers")
        lookup_columns = [
            self._first_remote_column("suppliers", [name])
            for name in self.SUPPLIER_LOOKUP_COLUMNS
        ]
        lookup_columns = [item for item in lookup_columns if item]
        if not lookup_columns:
            return {}

        for lookup_column in lookup_columns:
            for chunk in self._chunked(values, 150):
                rows = self.storage.fetch_remote_rows_in(
                    table="suppliers",
                    column=str(lookup_column),
                    values=list(chunk),
                    limit=max(len(chunk) * 30, 1000),
                    columns=columns,
                )
                if rows:
                    matched_rows.extend(rows)
                    if persist_clone:
                        self.storage.upsert_rows(table="suppliers", rows=rows)

        result: dict[str, int] = {}
        for row in matched_rows:
            supplier_id = self._to_int(find_value(row, ["id"]))
            if supplier_id is None:
                continue
            for raw_value in [
                find_value(row, ["matchcode"]),
                find_value(row, ["description"]),
                find_value(row, ["fulldescription"]),
            ]:
                normalized = normalize_brand(str(raw_value or ""))
                if normalized and normalized in values and normalized not in result:
                    result[normalized] = supplier_id
        return result

    def _bulk_lookup_local_articles(self, resolutions: list[PairResolution]) -> dict[tuple[int | None, str], dict[str, Any]]:
        return self._bulk_lookup_articles_generic(resolutions=resolutions, remote=False)

    def _bulk_lookup_remote_articles(
        self,
        resolutions: list[PairResolution],
        *,
        persist_clone: bool,
    ) -> dict[tuple[int | None, str], dict[str, Any]]:
        return self._bulk_lookup_articles_generic(resolutions=resolutions, remote=True, persist_clone=persist_clone)

    def _bulk_lookup_articles_generic(
        self,
        *,
        resolutions: list[PairResolution],
        remote: bool,
        persist_clone: bool = False,
    ) -> dict[tuple[int | None, str], dict[str, Any]]:
        pending = [item for item in resolutions if item.supplier_id is not None]
        if not pending:
            return {}

        result: dict[tuple[int | None, str], dict[str, Any]] = {}
        table_order = ("article_numbers", "articles")

        article_values = sorted(
            {
                str(variant or "").strip()
                for item in pending
                for variant in item.bucket.article_variants
                if str(variant or "").strip()
            }
            | {item.bucket.normalized_article for item in pending if item.bucket.normalized_article}
        )
        if not article_values:
            return {}

        for table in table_order:
            candidate_columns = self.storage.get_remote_columns(table) if remote else list(self.storage.get_local_columns(table))
            article_column = self._resolve_column_name(candidate_columns, self.ARTICLE_NUMBER_COLUMNS)
            if not article_column:
                continue
            selected_columns = list(candidate_columns)

            rows: list[dict[str, Any]] = []
            for chunk in self._chunked(article_values, 200):
                if remote:
                    rows_chunk = self.storage.fetch_remote_rows_in(
                        table=table,
                        column=article_column,
                        values=list(chunk),
                        limit=max(len(chunk) * 100, 5000),
                        columns=selected_columns,
                    )
                else:
                    rows_chunk = self.storage.fetch_local_rows_in(
                        table=table,
                        column=article_column,
                        values=list(chunk),
                        limit=max(len(chunk) * 100, 5000),
                        columns=selected_columns,
                    )
                rows.extend(rows_chunk)

            if remote and rows and persist_clone:
                self.storage.upsert_rows(table=table, rows=rows)

            variant_by_supplier: dict[int, set[str]] = {}
            for item in pending:
                if item.supplier_id is None:
                    continue
                variant_by_supplier.setdefault(int(item.supplier_id), set()).update(
                    {normalize_article(v) for v in item.bucket.article_variants if str(v or "").strip()}
                )
                variant_by_supplier[int(item.supplier_id)].add(item.bucket.normalized_article)

            for row in rows:
                supplier_id = self._to_int(find_value(row, list(self.ARTICLE_SUPPLIER_COLUMNS)))
                if supplier_id is None:
                    continue
                article_number = self._extract_article_number(row)
                normalized = normalize_article(article_number)
                if not normalized:
                    continue
                if normalized not in variant_by_supplier.get(int(supplier_id), set()):
                    continue
                key = (supplier_id, normalized)
                if key not in result:
                    result[key] = row

            unresolved = [item for item in pending if (item.supplier_id, item.bucket.normalized_article) not in result]
            if not unresolved:
                break
            pending = unresolved
        return result

    def _bulk_related_enrichment(self, resolutions: list[PairResolution], *, persist_clone: bool) -> int:
        keys = [(item.supplier_id, item.canonical_article_number) for item in resolutions if item.supplier_id and item.canonical_article_number]
        if not keys:
            return 0

        unique_keys = sorted(set(keys))
        processed = 0

        for table in self.RELATED_TABLES:
            if table == "article_m":
                continue
            remote_columns = self.storage.get_remote_columns(table)
            supplier_column = self._resolve_column_name(remote_columns, ["supplierId", "supplierid", "SupplierId", "supplier_id", "supplier"])
            number_column = self._resolve_column_name(
                remote_columns,
                ["DataSupplierArticleNumber", "datasupplierarticlenumber", "PartsDataSupplierArticleNumber", "articlenumber", "article", "number"],
            )
            if not supplier_column or not number_column:
                continue

            table_rows: list[dict[str, Any]] = []
            for chunk in self._chunked(unique_keys, 100):
                rows = self.storage.fetch_remote_rows_by_composite_keys(
                    table=table,
                    first_column=supplier_column,
                    second_column=number_column,
                    keys=list(chunk),
                    limit=100000,
                    columns=remote_columns,
                )
                if rows:
                    table_rows.extend(rows)

            if table_rows and persist_clone:
                self.storage.upsert_rows(table=table, rows=table_rows)

        processed = len(unique_keys)
        return processed

    def _prepare_product_updates(
        self,
        *,
        resolutions: list[PairResolution],
        product_map: dict[str, Product],
        product_updates: dict[str, Product],
        summary: RawOfferEnrichmentSummary,
    ) -> int:
        linked = 0
        for item in resolutions:
            if not item.article_key:
                continue
            if not item.bucket.matched_product_ids:
                continue

            lookup = ArticleLookupResult(
                found=True,
                normalized_brand=item.bucket.normalized_brand,
                normalized_article=item.bucket.normalized_article,
                supplier_id=item.supplier_id,
                article_key=item.article_key,
                article_id=item.article_id,
                canonical_article_number=item.canonical_article_number,
                canonical_brand=item.bucket.sample_brand,
                supplier_source=item.source,
                article_source=item.source,
                warnings=item.warnings,
                raw_local_refs={},
                populated_tables={},
            )

            for product_id in sorted(item.bucket.matched_product_ids):
                product = product_map.get(product_id)
                if product is None:
                    summary.failed += 1
                    continue

                self.product_linker.link_product_with_lookup(
                    product=product,
                    lookup=lookup,
                    normalized_brand=item.bucket.normalized_brand,
                    normalized_article=item.bucket.normalized_article,
                    dry_run=True,
                )
                key = str(product.id)
                if key not in product_updates:
                    linked += 1
                product_updates[key] = product
        return linked

    def _bulk_save_products(self, products: list[Product]) -> None:
        if not products:
            return
        with transaction.atomic():
            Product.objects.bulk_update(
                products,
                [
                    "normalized_brand",
                    "normalized_article",
                    "autodb_supplier_id",
                    "autodb_article_id",
                    "autodb_article_number",
                    "autodb_article_key",
                    "catalog_source",
                    "updated_at",
                ],
                batch_size=500,
            )

    def _first_remote_column(self, table: str, candidates: list[str]) -> str | None:
        columns = self.storage.get_remote_columns(table)
        return self._resolve_column_name(columns, candidates)

    def _resolve_column_name(self, columns: list[str], candidates: Iterable[str]) -> str | None:
        by_lower = {str(item).lower(): str(item) for item in columns}
        for candidate in candidates:
            found = by_lower.get(str(candidate).lower())
            if found:
                return found
        return None

    def _extract_article_number(self, row: dict[str, Any]) -> str:
        for value in [find_value(row, list(self.ARTICLE_NUMBER_COLUMNS))]:
            candidate = str(value or "").strip()
            if candidate:
                return candidate.replace(" ", "")
        return ""

    def _compose_article_key(self, supplier_id: int | None, article_number: str) -> str:
        if supplier_id is None:
            return ""
        number = str(article_number or "").replace(" ", "")
        if not number:
            return ""
        return f"{supplier_id}:{number}"

    def _chunked(self, values: list[Any], size: int) -> Iterable[list[Any]]:
        safe_size = max(int(size), 1)
        for idx in range(0, len(values), safe_size):
            yield values[idx : idx + safe_size]

    def _to_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _single_scope(self, values: list[str | None]) -> str | None:
        unique = {str(item) for item in values if item}
        if len(unique) == 1:
            return next(iter(unique))
        return None
