from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError
from django.utils.translation import gettext as _

from apps.autocatalog.services import (
    AutocatalogImportSummary,
    UtrArticleDetailResolverService,
    UtrArticleResolveSummary,
    UtrAutocatalogImportService,
)
from apps.catalog.models import Product
from apps.supplier_imports.selectors import get_supplier_integration_by_code

from . import reporting
from .options import normalize_options
from .types import CommandOutput, UtrImportCommandOptions


def run_autocatalog_import_flow(
    *,
    raw_options: Mapping[str, Any],
    force_refresh: bool,
    output: CommandOutput,
) -> None:
    integration = get_supplier_integration_by_code(source_code="utr")
    if not integration.access_token:
        raise CommandError(_("UTR access token отсутствует. Сначала обновите токен интеграции UTR."))
    options = normalize_options(raw_options)

    resolver = UtrArticleDetailResolverService()

    product_detail_ids = collect_product_detail_ids()
    reporting.write_product_detail_ids_available(output, count=len(product_detail_ids))

    mapped_detail_ids: list[str] = [] if options.products_only else resolver.collect_detail_ids()
    if not options.products_only:
        reporting.write_mapped_detail_ids_available(output, count=len(mapped_detail_ids))

    should_run_resolve = not options.products_only and (
        options.resolve_utr_articles or (not product_detail_ids and not mapped_detail_ids)
    )
    if should_run_resolve:
        reporting.write_resolve_started(output)
        reporting.write_resolve_runtime(output)
        reporting.write_resolve_progress(output, label="before", progress=resolver.collect_progress())

        resolve_summary = run_resolve_phase(
            resolver=resolver,
            access_token=integration.access_token,
            options=options,
            output=output,
        )
        reporting.write_resolve_summary(output, summary=resolve_summary)
        reporting.write_resolve_progress(output, label="after", progress=resolver.collect_progress())

        if resolve_summary.stopped_due_to_circuit_breaker > 0:
            reporting.write_resolve_circuit_breaker_stop(output)
            return

        mapped_detail_ids = resolver.collect_detail_ids()
        reporting.write_mapped_detail_ids_available(output, count=len(mapped_detail_ids))

        # Access token may be refreshed/re-obtained inside batch resolve flow.
        integration = get_supplier_integration_by_code(source_code="utr")

    if options.resolve_only:
        reporting.write_resolve_only_success(output)
        return

    detail_ids = merge_detail_ids(
        product_detail_ids=product_detail_ids,
        mapped_detail_ids=mapped_detail_ids,
        limit=options.limit,
        offset=options.offset,
    )
    if not detail_ids:
        reporting.write_no_detail_ids_warning(output)
        return

    reporting.write_detail_ids_to_process(output, count=len(detail_ids), offset=options.offset, limit=options.limit)
    reporting.write_import_runtime(output, batch_size=options.batch_size, force_refresh=force_refresh)

    import_service = UtrAutocatalogImportService()
    summary = AutocatalogImportSummary()
    total_detail_ids = len(detail_ids)

    for chunk_index, start in enumerate(range(0, total_detail_ids, options.batch_size), start=1):
        chunk = detail_ids[start : start + options.batch_size]
        reporting.write_chunk_started(output, chunk_index=chunk_index, start=start, size=len(chunk))

        def _chunk_progress(
            processed: int,
            _chunk_total: int,
            detail_id: str,
            *,
            base_offset: int = start,
        ) -> None:
            reporting.write_progress(output, processed=base_offset + processed, total=total_detail_ids, detail_id=detail_id)

        batch_summary = import_service.import_from_detail_ids(
            detail_ids=chunk,
            access_token=integration.access_token,
            on_error=lambda detail_id, message: reporting.write_import_error(
                output,
                detail_id=detail_id,
                message=message,
            ),
            on_progress=_chunk_progress,
            continue_on_error=True,
            force_refresh=force_refresh,
        )
        accumulate_import_summary(total=summary, batch=batch_summary)

        if batch_summary.stopped_due_to_circuit_breaker > 0:
            reporting.write_applicability_circuit_breaker_stop(output)
            break

    reporting.write_import_result(output, stopped_due_to_circuit_breaker=summary.stopped_due_to_circuit_breaker)
    reporting.write_summary_dict(output, summary=summary.to_dict())


def collect_product_detail_ids() -> list[str]:
    queryset = (
        Product.objects.exclude(utr_detail_id__isnull=True)
        .exclude(utr_detail_id="")
        .values_list("utr_detail_id", flat=True)
        .distinct()
        .order_by("utr_detail_id")
    )
    return [value for value in queryset if str(value).isdigit()]


def merge_detail_ids(
    *,
    product_detail_ids: list[str],
    mapped_detail_ids: list[str],
    limit: int | None,
    offset: int,
) -> list[str]:
    merged = sorted({*product_detail_ids, *mapped_detail_ids}, key=int)
    if offset > 0:
        merged = merged[offset:]
    if limit and limit > 0:
        merged = merged[:limit]
    return merged


def run_resolve_phase(
    *,
    resolver: UtrArticleDetailResolverService,
    access_token: str,
    options: UtrImportCommandOptions,
    output: CommandOutput,
) -> UtrArticleResolveSummary:
    batch_limit = options.resolve_limit
    if not batch_limit or int(batch_limit) <= 0:
        batch_limit = max(int(getattr(settings, "UTR_BATCH_SIZE", 25)), 1)

    total = UtrArticleResolveSummary()
    batch_index = 0
    batch_offset = options.resolve_offset

    while True:
        batch_index += 1
        summary = resolver.resolve_from_raw_offers(
            access_token=access_token,
            limit=batch_limit,
            offset=batch_offset,
            retry_unresolved=options.retry_unresolved,
            on_error=lambda pair, message: reporting.write_resolve_error(output, pair=pair, message=message),
            on_batch=lambda event: reporting.write_resolve_search_batch(output, event=event),
        )
        if summary.article_pairs_total == 0:
            if batch_index == 1:
                reporting.write_resolve_candidates_not_found(output)
            break

        reporting.write_resolve_batch_summary(output, batch_index=batch_index, summary=summary)
        accumulate_resolve_summary(total=total, batch=summary)

        if not options.resolve_until_empty:
            break
        if summary.article_pairs_total < batch_limit:
            break

        batch_offset = 0

    return total


def accumulate_resolve_summary(
    *,
    total: UtrArticleResolveSummary,
    batch: UtrArticleResolveSummary,
) -> None:
    total.article_pairs_total += batch.article_pairs_total
    total.article_pairs_processed += batch.article_pairs_processed
    total.resolved_created += batch.resolved_created
    total.resolved_updated += batch.resolved_updated
    total.already_resolved += batch.already_resolved
    total.unresolved_created += batch.unresolved_created
    total.unresolved_updated += batch.unresolved_updated
    total.empty_results += batch.empty_results
    total.ambiguous_results += batch.ambiguous_results
    total.failed_requests += batch.failed_requests
    total.stopped_due_to_circuit_breaker += batch.stopped_due_to_circuit_breaker
    total.resolve_batches_sent_total += batch.resolve_batches_sent_total
    total.resolve_pairs_sent_total += batch.resolve_pairs_sent_total
    total.resolve_pairs_resolved_total += batch.resolve_pairs_resolved_total
    total.resolve_pairs_unresolved_total += batch.resolve_pairs_unresolved_total
    total.resolve_pairs_ambiguous_total += batch.resolve_pairs_ambiguous_total
    total.resolve_batch_failures_total += batch.resolve_batch_failures_total
    total.resolve_batch_auth_failures_total += batch.resolve_batch_auth_failures_total
    total.resolve_pairs_auth_failures_total += batch.resolve_pairs_auth_failures_total
    total.resolve_pairs_transport_failures_total += batch.resolve_pairs_transport_failures_total
    total.resolve_pairs_supplier_errors_total += batch.resolve_pairs_supplier_errors_total
    total.stage_primary_brandless_attempted_total += batch.stage_primary_brandless_attempted_total
    total.stage_primary_brandless_resolved_total += batch.stage_primary_brandless_resolved_total
    total.stage_fallback_brandless_attempted_total += batch.stage_fallback_brandless_attempted_total
    total.stage_fallback_brandless_resolved_total += batch.stage_fallback_brandless_resolved_total
    total.stage_primary_branded_attempted_total += batch.stage_primary_branded_attempted_total
    total.stage_primary_branded_resolved_total += batch.stage_primary_branded_resolved_total
    total.stage_fallback_branded_attempted_total += batch.stage_fallback_branded_attempted_total
    total.stage_fallback_branded_resolved_total += batch.stage_fallback_branded_resolved_total


def accumulate_import_summary(
    *,
    total: AutocatalogImportSummary,
    batch: AutocatalogImportSummary,
) -> None:
    total.detail_ids_total += batch.detail_ids_total
    total.detail_ids_processed += batch.detail_ids_processed
    total.detail_ids_failed += batch.detail_ids_failed
    total.detail_ids_skipped_cached += batch.detail_ids_skipped_cached
    total.detail_ids_skipped_disabled += batch.detail_ids_skipped_disabled
    total.detail_ids_empty_applicability += batch.detail_ids_empty_applicability
    total.stopped_due_to_circuit_breaker += batch.stopped_due_to_circuit_breaker
    total.makes_created += batch.makes_created
    total.models_created += batch.models_created
    total.modifications_created += batch.modifications_created
    total.mappings_created += batch.mappings_created
