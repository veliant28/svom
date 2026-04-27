from __future__ import annotations

import logging

from django.conf import settings

from apps.autocatalog.models import UtrArticleDetailMap
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError
from apps.supplier_imports.services.integrations.utr_client import UtrClient

from . import diagnostics, persistence, planner, selector, stages
from .types import ResolveContext, UtrArticleResolveProgress, UtrArticleResolveSummary

logger = logging.getLogger(__name__)


class UtrArticleDetailResolverService:
    STAGE_BRANDLESS_FIRST = "brandless_first"
    STAGE_BRANDED_FIRST = "branded_first"

    def __init__(self, *, client: UtrClient | None = None):
        self.client = client or UtrClient()
        self._search_cache: dict[tuple[str, str], list[dict]] = {}
        self._search_query_outcomes: dict[tuple[str, str], dict] = {}
        self.resolve_batch_size = max(int(getattr(settings, "UTR_RESOLVE_BATCH_SIZE", 10)), 1)
        raw_stage_order = str(getattr(settings, "UTR_RESOLVE_STAGE_ORDER", self.STAGE_BRANDED_FIRST)).strip().lower()
        if raw_stage_order not in {self.STAGE_BRANDLESS_FIRST, self.STAGE_BRANDED_FIRST}:
            raw_stage_order = self.STAGE_BRANDED_FIRST
        self.resolve_stage_order = raw_stage_order

    def resolve_from_raw_offers(
        self,
        *,
        access_token: str,
        limit: int | None = None,
        offset: int = 0,
        retry_unresolved: bool = False,
        on_error: callable | None = None,
        on_batch: callable | None = None,
    ) -> UtrArticleResolveSummary:
        if retry_unresolved:
            pairs = self._collect_unresolved_pairs(limit=limit, offset=offset)
        else:
            pairs = self._collect_article_brand_pairs(limit=limit, offset=offset, exclude_existing=True)
        summary = UtrArticleResolveSummary(article_pairs_total=len(pairs))
        contexts: list[ResolveContext] = []

        for pair in pairs:
            existing = UtrArticleDetailMap.objects.filter(
                normalized_article=pair["normalized_article"],
                normalized_brand=pair["normalized_brand"],
            ).first()
            if existing and existing.utr_detail_id:
                summary.already_resolved += 1
                continue
            contexts.append(
                ResolveContext(
                    pair=pair,
                    stages=self._build_search_stages(pair=pair),
                )
            )

        if contexts:
            self._resolve_contexts_with_batch_search(
                access_token=access_token,
                contexts=contexts,
                summary=summary,
                on_batch=on_batch,
            )

        processed_total = summary.already_resolved
        for context in contexts:
            pair = context.pair
            if context.status == "pending":
                continue
            processed_total += 1

            if context.status == "resolved" and context.detail_id:
                created = self._upsert_mapping(
                    article=pair["article"],
                    normalized_article=pair["normalized_article"],
                    brand_name=pair["brand_name"],
                    normalized_brand=pair["normalized_brand"],
                    utr_detail_id=context.detail_id,
                )
                if created:
                    summary.resolved_created += 1
                else:
                    summary.resolved_updated += 1
                summary.resolve_pairs_resolved_total += 1
                self._increment_stage_resolved_counter(summary=summary, stage_name=context.resolved_stage)
                self._enrich_products_from_resolved_detail(context=context, summary=summary)
                continue

            if context.status == "ambiguous":
                summary.ambiguous_results += 1
                summary.resolve_pairs_ambiguous_total += 1
                self._track_unresolved(pair=pair, summary=summary)
                continue

            if context.status == "auth_failure":
                summary.failed_requests += 1
                summary.resolve_pairs_auth_failures_total += 1
                if on_error is not None:
                    on_error(pair, context.error_message or "UTR auth failure during batch resolve.")
                continue

            if context.status == "transport_failure":
                summary.failed_requests += 1
                summary.resolve_pairs_transport_failures_total += 1
                if on_error is not None:
                    on_error(pair, context.error_message or "UTR transport failure during batch resolve.")
                continue

            if context.status == "supplier_error":
                summary.failed_requests += 1
                summary.resolve_pairs_supplier_errors_total += 1
                if on_error is not None:
                    on_error(pair, context.error_message or "UTR supplier API error during batch resolve.")
                continue

            if context.status == "failed":
                summary.failed_requests += 1
                summary.resolve_pairs_unresolved_total += 1
                self._track_unresolved(pair=pair, summary=summary)
                if on_error is not None:
                    on_error(pair, context.error_message or "Batch search request failed.")
                continue

            summary.empty_results += 1
            summary.resolve_pairs_unresolved_total += 1
            self._track_unresolved(pair=pair, summary=summary)

        summary.article_pairs_processed = min(processed_total, summary.article_pairs_total)
        return summary

    def collect_progress(self) -> UtrArticleResolveProgress:
        return diagnostics.collect_progress()

    def collect_detail_ids(self, *, limit: int | None = None, offset: int = 0) -> list[str]:
        queryset = (
            UtrArticleDetailMap.objects.exclude(utr_detail_id="")
            .values_list("utr_detail_id", flat=True)
            .distinct()
            .order_by("utr_detail_id")
        )
        if offset > 0:
            queryset = queryset[offset:]
        if limit and limit > 0:
            queryset = queryset[:limit]
        return [value for value in queryset if str(value).isdigit()]

    # Back-compat private wrappers
    def _collect_article_brand_pairs(
        self,
        *,
        limit: int | None,
        offset: int,
        exclude_existing: bool,
    ) -> list[dict[str, str]]:
        return planner.collect_article_brand_pairs(limit=limit, offset=offset, exclude_existing=exclude_existing)

    def _collect_unresolved_pairs(self, *, limit: int | None, offset: int) -> list[dict[str, str]]:
        return planner.collect_unresolved_pairs(limit=limit, offset=offset)

    def _count_raw_pairs(self) -> int:
        return planner.count_raw_pairs()

    def _build_search_stages(self, *, pair: dict[str, str]) -> list[dict[str, str]]:
        return planner.build_search_stages(
            pair=pair,
            resolve_stage_order=self.resolve_stage_order,
            stage_brandless_first=self.STAGE_BRANDLESS_FIRST,
            stage_branded_first=self.STAGE_BRANDED_FIRST,
        )

    def _resolve_contexts_with_batch_search(
        self,
        *,
        access_token: str,
        contexts: list[ResolveContext],
        summary: UtrArticleResolveSummary,
        on_batch: callable | None = None,
    ) -> None:
        stages.resolve_contexts_with_batch_search(
            service=self,
            access_token=access_token,
            contexts=contexts,
            summary=summary,
            on_batch=on_batch,
        )

    def _collect_stage_queries(
        self,
        *,
        contexts: list[ResolveContext],
        stage_index: int,
    ) -> list[dict[str, str]]:
        return planner.collect_stage_queries(
            contexts=contexts,
            stage_index=stage_index,
            search_cache=self._search_cache,
            search_query_outcomes=self._search_query_outcomes,
        )

    def _fetch_stage_queries_in_batches(
        self,
        *,
        access_token: str,
        stage_name: str,
        queries: list[dict[str, str]],
        summary: UtrArticleResolveSummary,
        on_batch: callable | None = None,
    ) -> tuple[dict[tuple[str, str], dict], bool, str]:
        return stages.fetch_stage_queries_in_batches(
            service=self,
            access_token=access_token,
            stage_name=stage_name,
            queries=queries,
            summary=summary,
            on_batch=on_batch,
        )

    def _build_batch_payload_item(self, *, query: dict[str, str]) -> dict[str, str]:
        return planner.build_batch_payload_item(query=query)

    def _classify_exception_kind(self, *, exc: SupplierClientError) -> str:
        return diagnostics.classify_exception_kind(client=self.client, exc=exc)

    def _classify_row_error_kind(self, *, error_message: str) -> str:
        return diagnostics.classify_row_error_kind(error_message=error_message)

    def _increment_stage_attempt_counter(self, *, summary: UtrArticleResolveSummary, stage_name: str) -> None:
        diagnostics.increment_stage_attempt_counter(summary=summary, stage_name=stage_name)

    def _increment_stage_resolved_counter(self, *, summary: UtrArticleResolveSummary, stage_name: str) -> None:
        diagnostics.increment_stage_resolved_counter(summary=summary, stage_name=stage_name)

    def _stage_counter_field(self, *, stage_name: str, suffix: str) -> str:
        return diagnostics.stage_counter_field(stage_name=stage_name, suffix=suffix)

    def _select_candidate_ids(self, *, details: list[dict], normalized_article: str, normalized_brand: str) -> list[str]:
        return selector.select_candidate_ids(
            details=details,
            normalized_article=normalized_article,
            normalized_brand=normalized_brand,
        )

    def _upsert_mapping(
        self,
        *,
        article: str,
        normalized_article: str,
        brand_name: str,
        normalized_brand: str,
        utr_detail_id: str,
    ) -> bool:
        return persistence.upsert_mapping(
            article=article,
            normalized_article=normalized_article,
            brand_name=brand_name,
            normalized_brand=normalized_brand,
            utr_detail_id=utr_detail_id,
        )

    def _track_unresolved(self, *, pair: dict[str, str], summary: UtrArticleResolveSummary) -> None:
        persistence.track_unresolved(pair=pair, summary=summary, upsert_func=self._upsert_mapping)

    def _enrich_products_from_resolved_detail(self, *, context: ResolveContext, summary: UtrArticleResolveSummary) -> None:
        if not bool(getattr(settings, "UTR_RESOLVE_ENRICH_PRODUCTS_FROM_SEARCH", True)):
            return
        detail = context.detail_payload
        if not isinstance(detail, dict):
            return
        try:
            from apps.catalog.services.utr_product_enrichment import apply_utr_search_detail_to_matching_products

            result = apply_utr_search_detail_to_matching_products(
                article=context.pair["article"],
                normalized_article=context.pair["normalized_article"],
                brand_name=context.pair["brand_name"],
                normalized_brand=context.pair["normalized_brand"],
                detail=detail,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "utr_article_detail_product_enrichment_failed article=%s brand=%s detail_id=%s error=%s",
                context.pair.get("article"),
                context.pair.get("brand_name"),
                context.detail_id,
                exc,
            )
            return
        summary.resolved_products_enriched_total += int(result.get("products_enriched", 0))
        summary.resolved_product_images_created_total += int(result.get("created_images", 0))
