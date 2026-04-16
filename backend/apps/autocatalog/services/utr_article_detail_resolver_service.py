from __future__ import annotations

from dataclasses import asdict, dataclass

from django.conf import settings
from django.db import transaction

from apps.autocatalog.models import UtrArticleDetailMap
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError
from apps.supplier_imports.services.integrations.utr_client import UtrClient


@dataclass
class UtrArticleResolveSummary:
    article_pairs_total: int = 0
    article_pairs_processed: int = 0
    resolved_created: int = 0
    resolved_updated: int = 0
    already_resolved: int = 0
    unresolved_created: int = 0
    unresolved_updated: int = 0
    empty_results: int = 0
    ambiguous_results: int = 0
    failed_requests: int = 0
    stopped_due_to_circuit_breaker: int = 0
    resolve_batches_sent_total: int = 0
    resolve_pairs_sent_total: int = 0
    resolve_pairs_resolved_total: int = 0
    resolve_pairs_unresolved_total: int = 0
    resolve_pairs_ambiguous_total: int = 0
    resolve_batch_failures_total: int = 0
    resolve_batch_auth_failures_total: int = 0
    resolve_pairs_auth_failures_total: int = 0
    resolve_pairs_transport_failures_total: int = 0
    resolve_pairs_supplier_errors_total: int = 0
    stage_primary_brandless_attempted_total: int = 0
    stage_primary_brandless_resolved_total: int = 0
    stage_fallback_brandless_attempted_total: int = 0
    stage_fallback_brandless_resolved_total: int = 0
    stage_primary_branded_attempted_total: int = 0
    stage_primary_branded_resolved_total: int = 0
    stage_fallback_branded_attempted_total: int = 0
    stage_fallback_branded_resolved_total: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class UtrArticleResolveProgress:
    raw_pairs_total: int = 0
    mapped_pairs_total: int = 0
    mapped_pairs_resolved: int = 0
    mapped_pairs_unresolved: int = 0
    raw_pairs_unattempted: int = 0
    raw_pairs_unresolved_total: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class _ResolveContext:
    pair: dict[str, str]
    stages: list[dict[str, str]]
    status: str = "pending"
    detail_id: str = ""
    resolved_stage: str = ""
    auth_failed: bool = False
    transport_failed: bool = False
    supplier_error: bool = False
    error_message: str = ""


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
        contexts: list[_ResolveContext] = []

        for pair in pairs:
            existing = UtrArticleDetailMap.objects.filter(
                normalized_article=pair["normalized_article"],
                normalized_brand=pair["normalized_brand"],
            ).first()
            if existing and existing.utr_detail_id:
                summary.already_resolved += 1
                continue
            contexts.append(
                _ResolveContext(
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
        raw_pairs_total = self._count_raw_pairs()
        mapped_pairs_total = UtrArticleDetailMap.objects.count()
        mapped_pairs_resolved = UtrArticleDetailMap.objects.exclude(utr_detail_id="").count()
        mapped_pairs_unresolved = max(0, mapped_pairs_total - mapped_pairs_resolved)

        return UtrArticleResolveProgress(
            raw_pairs_total=raw_pairs_total,
            mapped_pairs_total=mapped_pairs_total,
            mapped_pairs_resolved=mapped_pairs_resolved,
            mapped_pairs_unresolved=mapped_pairs_unresolved,
            raw_pairs_unattempted=max(0, raw_pairs_total - mapped_pairs_total),
            raw_pairs_unresolved_total=max(0, raw_pairs_total - mapped_pairs_resolved),
        )

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

    def _collect_article_brand_pairs(
        self,
        *,
        limit: int | None,
        offset: int,
        exclude_existing: bool,
    ) -> list[dict[str, str]]:
        existing_keys: set[tuple[str, str]] = set()
        if exclude_existing:
            existing_keys = set(
                UtrArticleDetailMap.objects.values_list(
                    "normalized_article",
                    "normalized_brand",
                )
            )

        queryset = (
            SupplierRawOffer.objects.filter(source__code="utr")
            .exclude(external_sku="")
            .values("external_sku", "article", "brand_name")
            .distinct()
            .order_by("external_sku", "article", "brand_name")
        )

        pairs: list[dict[str, str]] = []
        seen_keys: set[tuple[str, str]] = set()
        skipped = 0
        for row in queryset.iterator(chunk_size=2000):
            article = str(row.get("external_sku") or "").strip()
            if not article:
                continue

            normalized_article = normalize_article(article)
            if not normalized_article:
                continue

            brand_name = str(row.get("brand_name") or "").strip()
            normalized_brand = normalize_brand(brand_name)
            key = (normalized_article, normalized_brand)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            if exclude_existing and key in existing_keys:
                continue
            if skipped < offset:
                skipped += 1
                continue

            fallback_article = str(row.get("article") or "").strip()
            pairs.append(
                {
                    "article": article,
                    "fallback_article": fallback_article,
                    "normalized_article": normalized_article,
                    "brand_name": brand_name,
                    "normalized_brand": normalized_brand,
                }
            )
            if limit and limit > 0 and len(pairs) >= limit:
                break
        return pairs

    def _collect_unresolved_pairs(self, *, limit: int | None, offset: int) -> list[dict[str, str]]:
        queryset = (
            UtrArticleDetailMap.objects.filter(utr_detail_id="")
            .values("article", "brand_name", "normalized_article", "normalized_brand")
            .order_by("normalized_article", "normalized_brand")
        )
        if offset > 0:
            queryset = queryset[offset:]
        if limit and limit > 0:
            queryset = queryset[:limit]

        pairs: list[dict[str, str]] = []
        for row in queryset:
            article = str(row.get("article") or "").strip()
            normalized_article = str(row.get("normalized_article") or "").strip()
            if not article or not normalized_article:
                continue
            brand_name = str(row.get("brand_name") or "").strip()
            pairs.append(
                {
                    "article": article,
                    "fallback_article": "",
                    "normalized_article": normalized_article,
                    "brand_name": brand_name,
                    "normalized_brand": str(row.get("normalized_brand") or "").strip(),
                }
            )
        return pairs

    def _count_raw_pairs(self) -> int:
        queryset = (
            SupplierRawOffer.objects.filter(source__code="utr")
            .exclude(external_sku="")
            .values("external_sku", "brand_name")
            .distinct()
            .order_by("external_sku", "brand_name")
        )
        seen_keys: set[tuple[str, str]] = set()
        for row in queryset.iterator(chunk_size=2000):
            article = str(row.get("external_sku") or "").strip()
            if not article:
                continue
            normalized_article = normalize_article(article)
            if not normalized_article:
                continue
            brand_name = str(row.get("brand_name") or "").strip()
            key = (normalized_article, normalize_brand(brand_name))
            seen_keys.add(key)
        return len(seen_keys)

    def _build_search_stages(self, *, pair: dict[str, str]) -> list[dict[str, str]]:
        article = str(pair.get("article") or "").strip()
        fallback_article = str(pair.get("fallback_article") or "").strip()
        brand = str(pair.get("brand_name") or "").strip()
        normalized_article = str(pair.get("normalized_article") or "").strip()
        normalized_fallback_article = normalize_article(fallback_article)
        has_fallback = bool(fallback_article and normalized_fallback_article and fallback_article != article)

        primary_brandless = {
            "name": "primary_brandless",
            "oem": article,
            "brand": "",
            "normalized_article": normalized_article,
        }
        fallback_brandless = {
            "name": "fallback_brandless",
            "oem": fallback_article,
            "brand": "",
            "normalized_article": normalized_fallback_article,
        }
        primary_branded = {
            "name": "primary_branded",
            "oem": article,
            "brand": brand,
            "normalized_article": normalized_article,
        }
        fallback_branded = {
            "name": "fallback_branded",
            "oem": fallback_article,
            "brand": brand,
            "normalized_article": normalized_fallback_article,
        }

        stages: list[dict[str, str]] = []
        if self.resolve_stage_order == self.STAGE_BRANDED_FIRST and brand:
            stages.append(primary_branded)
            if has_fallback:
                stages.append(fallback_branded)
            stages.append(primary_brandless)
            if has_fallback:
                stages.append(fallback_brandless)
            return stages

        stages.append(primary_brandless)
        if has_fallback:
            stages.append(fallback_brandless)
        if brand:
            stages.append(primary_branded)
            if has_fallback:
                stages.append(fallback_branded)
        return stages

    def _resolve_contexts_with_batch_search(
        self,
        *,
        access_token: str,
        contexts: list[_ResolveContext],
        summary: UtrArticleResolveSummary,
        on_batch: callable | None = None,
    ) -> None:
        max_stage_count = max((len(context.stages) for context in contexts), default=0)

        for stage_index in range(max_stage_count):
            stage_contexts = [
                context
                for context in contexts
                if context.status == "pending" and stage_index < len(context.stages)
            ]
            if not stage_contexts:
                continue

            stage_name = stage_contexts[0].stages[stage_index].get("name", f"stage_{stage_index + 1}")
            stage_queries = self._collect_stage_queries(contexts=stage_contexts, stage_index=stage_index)
            query_outcomes: dict[tuple[str, str], dict] = {}
            should_stop = False
            if stage_queries:
                query_outcomes, should_stop, access_token = self._fetch_stage_queries_in_batches(
                    access_token=access_token,
                    stage_name=stage_name,
                    queries=stage_queries,
                    summary=summary,
                    on_batch=on_batch,
                )

            for context in stage_contexts:
                if context.status != "pending":
                    continue
                query = context.stages[stage_index]
                stage_name_for_context = str(query.get("name") or "")
                self._increment_stage_attempt_counter(summary=summary, stage_name=stage_name_for_context)
                query_key = (query.get("oem", ""), query.get("brand", ""))
                outcome = query_outcomes.get(query_key)
                if outcome is not None:
                    status = str(outcome.get("status") or "")
                    if status == "auth_failure":
                        context.auth_failed = True
                        context.error_message = str(outcome.get("message") or context.error_message)
                        continue
                    if status == "transport_failure":
                        context.transport_failed = True
                        context.error_message = str(outcome.get("message") or context.error_message)
                        continue
                    if status == "supplier_error":
                        context.supplier_error = True
                        context.error_message = str(outcome.get("message") or context.error_message)
                        continue

                details = self._search_cache.get(query_key, [])
                detail_ids = self._select_candidate_ids(
                    details=details,
                    normalized_article=query.get("normalized_article", ""),
                    normalized_brand=context.pair.get("normalized_brand", ""),
                )
                if len(detail_ids) == 1:
                    context.status = "resolved"
                    context.detail_id = detail_ids[0]
                    context.resolved_stage = stage_name_for_context
                    continue
                if len(detail_ids) > 1:
                    context.status = "ambiguous"

            if should_stop:
                return

        for context in contexts:
            if context.status == "pending":
                if context.auth_failed:
                    context.status = "auth_failure"
                elif context.transport_failed:
                    context.status = "transport_failure"
                elif context.supplier_error:
                    context.status = "supplier_error"
                else:
                    context.status = "empty"

    def _collect_stage_queries(
        self,
        *,
        contexts: list[_ResolveContext],
        stage_index: int,
    ) -> list[dict[str, str]]:
        seen_keys: set[tuple[str, str]] = set()
        queries: list[dict[str, str]] = []
        for context in contexts:
            query = context.stages[stage_index]
            oem = str(query.get("oem") or "").strip()
            brand = str(query.get("brand") or "").strip()
            if not oem:
                continue
            key = (oem, brand)
            if key in seen_keys or key in self._search_cache or key in self._search_query_outcomes:
                continue
            seen_keys.add(key)
            queries.append({"oem": oem, "brand": brand})
        return queries

    def _fetch_stage_queries_in_batches(
        self,
        *,
        access_token: str,
        stage_name: str,
        queries: list[dict[str, str]],
        summary: UtrArticleResolveSummary,
        on_batch: callable | None = None,
    ) -> tuple[dict[tuple[str, str], dict], bool, str]:
        outcomes: dict[tuple[str, str], dict] = {}
        current_access_token = str(access_token or "").strip()

        for batch_index, start in enumerate(range(0, len(queries), self.resolve_batch_size), start=1):
            chunk = queries[start : start + self.resolve_batch_size]
            if not chunk:
                continue

            summary.resolve_batches_sent_total += 1
            summary.resolve_pairs_sent_total += len(chunk)

            try:
                payload = [self._build_batch_payload_item(query=item) for item in chunk]
                batch_result = self.client.search_details_batch(
                    access_token=current_access_token,
                    details=payload,
                    request_reason="autocatalog:resolve_article_detail_batch",
                )
                rows = batch_result.rows
                current_access_token = batch_result.access_token
            except SupplierClientError as exc:
                message = str(exc)
                summary.resolve_batch_failures_total += 1
                failure_kind = self._classify_exception_kind(exc=exc)
                if failure_kind == "auth_failure":
                    summary.resolve_batch_auth_failures_total += 1
                for item in chunk:
                    key = (str(item.get("oem") or "").strip(), str(item.get("brand") or "").strip())
                    outcomes[key] = {"status": failure_kind, "message": message}
                    self._search_query_outcomes[key] = {"status": failure_kind, "message": message}
                if on_batch is not None:
                    on_batch(
                        {
                            "stage": stage_name,
                            "batch_index": batch_index,
                            "batch_size": len(chunk),
                            "failed": True,
                            "failure_kind": failure_kind,
                            "message": message,
                        }
                    )
                if self.client.is_circuit_open_error(exc):
                    summary.stopped_due_to_circuit_breaker += 1
                    return outcomes, True, current_access_token
                continue

            error_count = 0
            details_non_empty = 0
            auth_row_errors = 0
            for item_index, item in enumerate(chunk):
                row = rows[item_index] if item_index < len(rows) and isinstance(rows[item_index], dict) else {}
                key = (str(item.get("oem") or "").strip(), str(item.get("brand") or "").strip())
                details_payload = row.get("details")
                if isinstance(details_payload, list):
                    normalized_details = [entry for entry in details_payload if isinstance(entry, dict)]
                    self._search_cache[key] = normalized_details
                    outcome = {"status": "ok", "details": normalized_details}
                    outcomes[key] = outcome
                    self._search_query_outcomes[key] = outcome
                    if normalized_details:
                        details_non_empty += 1
                    continue
                error_message = str(row.get("error") or "Unexpected batch item response").strip()
                row_failure_kind = self._classify_row_error_kind(error_message=error_message)
                if row_failure_kind == "auth_failure":
                    auth_row_errors += 1
                outcome = {"status": row_failure_kind, "message": error_message}
                outcomes[key] = outcome
                self._search_query_outcomes[key] = outcome
                error_count += 1

            if auth_row_errors > 0:
                summary.resolve_batch_auth_failures_total += 1

            if on_batch is not None:
                on_batch(
                    {
                        "stage": stage_name,
                        "batch_index": batch_index,
                        "batch_size": len(chunk),
                        "failed": False,
                        "details_non_empty": details_non_empty,
                        "errors_in_batch": error_count,
                        "auth_errors": auth_row_errors,
                        "auth_retry": bool(batch_result.auth_retry_performed),
                        "auth_method": str(batch_result.auth_retry_method),
                        "saved_pairs": max(len(chunk) - error_count, 0),
                    }
                )

        return outcomes, False, current_access_token

    def _build_batch_payload_item(self, *, query: dict[str, str]) -> dict[str, str]:
        payload = {"oem": str(query.get("oem") or "").strip()}
        brand = str(query.get("brand") or "").strip()
        if brand:
            payload["brand"] = brand
        return payload

    def _classify_exception_kind(self, *, exc: SupplierClientError) -> str:
        if self.client.is_auth_error(exc):
            return "auth_failure"
        if self.client.is_transport_error(exc):
            return "transport_failure"
        return "supplier_error"

    def _classify_row_error_kind(self, *, error_message: str) -> str:
        message = str(error_message or "").strip().lower()
        if any(marker in message for marker in ("expired jwt token", "invalid jwt token", "unauthorized", "auth")):
            return "auth_failure"
        return "supplier_error"

    def _increment_stage_attempt_counter(self, *, summary: UtrArticleResolveSummary, stage_name: str) -> None:
        field_name = self._stage_counter_field(stage_name=stage_name, suffix="attempted_total")
        if not field_name:
            return
        setattr(summary, field_name, int(getattr(summary, field_name, 0)) + 1)

    def _increment_stage_resolved_counter(self, *, summary: UtrArticleResolveSummary, stage_name: str) -> None:
        field_name = self._stage_counter_field(stage_name=stage_name, suffix="resolved_total")
        if not field_name:
            return
        setattr(summary, field_name, int(getattr(summary, field_name, 0)) + 1)

    def _stage_counter_field(self, *, stage_name: str, suffix: str) -> str:
        normalized = str(stage_name or "").strip().lower()
        mapping = {
            "primary_brandless": f"stage_primary_brandless_{suffix}",
            "fallback_brandless": f"stage_fallback_brandless_{suffix}",
            "primary_branded": f"stage_primary_branded_{suffix}",
            "fallback_branded": f"stage_fallback_branded_{suffix}",
        }
        return mapping.get(normalized, "")

    def _select_candidate_ids(self, *, details: list[dict], normalized_article: str, normalized_brand: str) -> list[str]:
        strict_ids: set[str] = set()
        relaxed_ids: set[str] = set()

        for item in details:
            detail_id = str(item.get("id") or "").strip()
            if not detail_id.isdigit():
                continue

            detail_article = normalize_article(str(item.get("article") or item.get("oem") or ""))
            detail_brand = normalize_brand(
                str(item.get("displayBrand") or (item.get("brand") or {}).get("name") or "")
            )

            if detail_article == normalized_article:
                relaxed_ids.add(detail_id)
                if not normalized_brand or not detail_brand or detail_brand == normalized_brand:
                    strict_ids.add(detail_id)

        if strict_ids:
            return sorted(strict_ids)
        return sorted(relaxed_ids)

    @transaction.atomic
    def _upsert_mapping(
        self,
        *,
        article: str,
        normalized_article: str,
        brand_name: str,
        normalized_brand: str,
        utr_detail_id: str,
    ) -> bool:
        mapping = UtrArticleDetailMap.objects.filter(
            normalized_article=normalized_article,
            normalized_brand=normalized_brand,
        ).first()
        if mapping is None:
            UtrArticleDetailMap.objects.create(
                article=article,
                normalized_article=normalized_article,
                brand_name=brand_name,
                normalized_brand=normalized_brand,
                utr_detail_id=utr_detail_id,
            )
            return True

        changed = False
        if mapping.article != article:
            mapping.article = article
            changed = True
        if mapping.brand_name != brand_name:
            mapping.brand_name = brand_name
            changed = True
        if mapping.utr_detail_id != utr_detail_id:
            mapping.utr_detail_id = utr_detail_id
            changed = True
        if changed:
            mapping.save(update_fields=("article", "brand_name", "utr_detail_id", "updated_at"))
        return False

    def _track_unresolved(self, *, pair: dict[str, str], summary: UtrArticleResolveSummary) -> None:
        unresolved_created = self._upsert_mapping(
            article=pair["article"],
            normalized_article=pair["normalized_article"],
            brand_name=pair["brand_name"],
            normalized_brand=pair["normalized_brand"],
            utr_detail_id="",
        )
        if unresolved_created:
            summary.unresolved_created += 1
        else:
            summary.unresolved_updated += 1
