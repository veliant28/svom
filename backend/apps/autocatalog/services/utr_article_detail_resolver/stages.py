from __future__ import annotations

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError

from .diagnostics import (
    classify_exception_kind,
    classify_row_error_kind,
    increment_stage_attempt_counter,
)
from .planner import build_batch_payload_item, collect_stage_queries
from .selector import select_candidate_ids


def resolve_contexts_with_batch_search(
    *,
    service,
    access_token: str,
    contexts,
    summary,
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
        stage_queries = collect_stage_queries(
            contexts=stage_contexts,
            stage_index=stage_index,
            search_cache=service._search_cache,
            search_query_outcomes=service._search_query_outcomes,
        )
        query_outcomes: dict[tuple[str, str], dict] = {}
        should_stop = False
        if stage_queries:
            query_outcomes, should_stop, access_token = fetch_stage_queries_in_batches(
                service=service,
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
            increment_stage_attempt_counter(summary=summary, stage_name=stage_name_for_context)
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

            details = service._search_cache.get(query_key, [])
            detail_ids = select_candidate_ids(
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


def fetch_stage_queries_in_batches(
    *,
    service,
    access_token: str,
    stage_name: str,
    queries: list[dict[str, str]],
    summary,
    on_batch: callable | None = None,
) -> tuple[dict[tuple[str, str], dict], bool, str]:
    outcomes: dict[tuple[str, str], dict] = {}
    current_access_token = str(access_token or "").strip()

    for batch_index, start in enumerate(range(0, len(queries), service.resolve_batch_size), start=1):
        chunk = queries[start : start + service.resolve_batch_size]
        if not chunk:
            continue

        summary.resolve_batches_sent_total += 1
        summary.resolve_pairs_sent_total += len(chunk)

        try:
            payload = [build_batch_payload_item(query=item) for item in chunk]
            batch_result = service.client.search_details_batch(
                access_token=current_access_token,
                details=payload,
                request_reason="autocatalog:resolve_article_detail_batch",
            )
            rows = batch_result.rows
            current_access_token = batch_result.access_token
        except SupplierClientError as exc:
            message = str(exc)
            summary.resolve_batch_failures_total += 1
            failure_kind = classify_exception_kind(client=service.client, exc=exc)
            if failure_kind == "auth_failure":
                summary.resolve_batch_auth_failures_total += 1
            for item in chunk:
                key = (str(item.get("oem") or "").strip(), str(item.get("brand") or "").strip())
                outcomes[key] = {"status": failure_kind, "message": message}
                service._search_query_outcomes[key] = {"status": failure_kind, "message": message}
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
            if service.client.is_circuit_open_error(exc):
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
                service._search_cache[key] = normalized_details
                outcome = {"status": "ok", "details": normalized_details}
                outcomes[key] = outcome
                service._search_query_outcomes[key] = outcome
                if normalized_details:
                    details_non_empty += 1
                continue
            error_message = str(row.get("error") or "Unexpected batch item response").strip()
            row_failure_kind = classify_row_error_kind(error_message=error_message)
            if row_failure_kind == "auth_failure":
                auth_row_errors += 1
            outcome = {"status": row_failure_kind, "message": error_message}
            outcomes[key] = outcome
            service._search_query_outcomes[key] = outcome
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
