from __future__ import annotations

from django.conf import settings
from django.utils.translation import gettext as _

from apps.autocatalog.services import UtrArticleResolveProgress, UtrArticleResolveSummary

from .types import CommandOutput


def write_product_detail_ids_available(output: CommandOutput, *, count: int) -> None:
    output.write(f"Product detail ids available: {count}")


def write_mapped_detail_ids_available(output: CommandOutput, *, count: int) -> None:
    output.write(f"Resolved article->detail mappings in DB: {count}")


def write_resolve_started(output: CommandOutput) -> None:
    output.write(_("Запуск резолва UTR detail_id по артикулу UTR..."))


def write_resolve_runtime(output: CommandOutput) -> None:
    output.write(
        f"[resolve-runtime] resolve_batch_size={getattr(settings, 'UTR_RESOLVE_BATCH_SIZE', 10)} "
        f"resolve_stage_order={getattr(settings, 'UTR_RESOLVE_STAGE_ORDER', 'branded_first')} "
        f"rate_limit_per_minute={getattr(settings, 'UTR_RATE_LIMIT_PER_MINUTE', 6)} "
        f"concurrency={getattr(settings, 'UTR_CONCURRENCY', 1)}"
    )


def write_resolve_summary(output: CommandOutput, *, summary: UtrArticleResolveSummary) -> None:
    output.write("[resolve-summary]")
    for key, value in summary.to_dict().items():
        output.write(f"  - {key}: {value}")


def write_resolve_progress(output: CommandOutput, *, label: str, progress: UtrArticleResolveProgress) -> None:
    output.write(f"[resolve-progress:{label}]")
    for key, value in progress.to_dict().items():
        output.write(f"  - {key}: {value}")


def write_resolve_circuit_breaker_stop(output: CommandOutput) -> None:
    output.write_warning(
        _(
            "UTR circuit breaker открыт во время resolve-фазы. "
            "Импорт остановлен до нового безопасного запуска после cooldown."
        )
    )
    output.write("[utr-stop] circuit_breaker_open=1 phase=resolve")


def write_resolve_only_success(output: CommandOutput) -> None:
    output.write_success(_("Резолв article->detail завершен (режим --resolve-only)."))


def write_no_detail_ids_warning(output: CommandOutput) -> None:
    output.write_warning(
        _("Не найдено utr_detail_id. Запустите с --resolve-utr-articles для резолва по артикулу UTR.")
    )


def write_detail_ids_to_process(output: CommandOutput, *, count: int, offset: int, limit: int | None) -> None:
    output.write(f"Detail ids to process: {count} (offset={offset}, limit={limit or 'all'})")


def write_import_runtime(output: CommandOutput, *, batch_size: int, force_refresh: bool) -> None:
    output.write(
        f"[utr-runtime] rate_limit_per_minute={getattr(settings, 'UTR_RATE_LIMIT_PER_MINUTE', 6)} "
        f"concurrency={getattr(settings, 'UTR_CONCURRENCY', 1)} "
        f"batch_size={batch_size} "
        f"applicability_enabled={int(bool(getattr(settings, 'UTR_APPLICABILITY_ENABLED', True)))} "
        f"force_refresh={int(force_refresh)} "
        f"unsafe_force_refresh={int(bool(getattr(settings, 'UTR_UNSAFE_ALLOW_FORCE_REFRESH', False)))}"
    )


def write_chunk_started(output: CommandOutput, *, chunk_index: int, start: int, size: int) -> None:
    output.write(f"[chunk {chunk_index}] start={start} size={size}")


def write_applicability_circuit_breaker_stop(output: CommandOutput) -> None:
    output.write_warning(
        _(
            "UTR circuit breaker открыт во время applicability-фазы. "
            "Дальнейшие запросы остановлены до нового запуска после cooldown."
        )
    )
    output.write("[utr-stop] circuit_breaker_open=1 phase=applicability")


def write_import_result(output: CommandOutput, *, stopped_due_to_circuit_breaker: int) -> None:
    if stopped_due_to_circuit_breaker > 0:
        output.write_warning(_("Импорт автокаталога остановлен circuit breaker."))
        return
    output.write_success(_("Импорт автокаталога завершен."))


def write_summary_dict(output: CommandOutput, *, summary: dict[str, int]) -> None:
    for key, value in summary.items():
        output.write(f"  - {key}: {value}")


def write_resolve_error(output: CommandOutput, *, pair: dict, message: str) -> None:
    article = pair.get("article") or ""
    brand = pair.get("brand_name") or ""
    output.write_warning(f"[resolve-error] article={article} brand={brand} message={message}")


def write_resolve_search_batch(output: CommandOutput, *, event: dict) -> None:
    stage = str(event.get("stage") or "")
    batch_index = int(event.get("batch_index") or 0)
    batch_size = int(event.get("batch_size") or 0)
    if bool(event.get("failed")):
        message = str(event.get("message") or "")
        failure_kind = str(event.get("failure_kind") or "")
        output.write_warning(
            f"[resolve-search-batch] stage={stage} batch={batch_index} size={batch_size} "
            f"failed=1 failure_kind={failure_kind} message={message}"
        )
        return

    if bool(event.get("auth_retry")):
        auth_method = str(event.get("auth_method") or "")
        saved_pairs = int(event.get("saved_pairs") or 0)
        output.write(
            f"[resolve-search-batch] stage={stage} batch={batch_index} size={batch_size} "
            f"auth_retry=1 method={auth_method} saved_pairs={saved_pairs}"
        )

    details_non_empty = int(event.get("details_non_empty") or 0)
    errors_in_batch = int(event.get("errors_in_batch") or 0)
    auth_errors = int(event.get("auth_errors") or 0)
    output.write(
        f"[resolve-search-batch] stage={stage} batch={batch_index} size={batch_size} "
        f"details_non_empty={details_non_empty} errors={errors_in_batch} auth_errors={auth_errors}"
    )


def write_resolve_batch_summary(output: CommandOutput, *, batch_index: int, summary: UtrArticleResolveSummary) -> None:
    output.write(
        f"[resolve-batch {batch_index}] pairs={summary.article_pairs_total} "
        f"processed={summary.article_pairs_processed} "
        f"resolved_created={summary.resolved_created} "
        f"resolved_updated={summary.resolved_updated} "
        f"unresolved_created={summary.unresolved_created} "
        f"unresolved_updated={summary.unresolved_updated} "
        f"failed={summary.failed_requests} "
        f"resolve_batches_sent={summary.resolve_batches_sent_total} "
        f"resolve_pairs_sent={summary.resolve_pairs_sent_total}"
    )


def write_resolve_candidates_not_found(output: CommandOutput) -> None:
    output.write("[resolve-batch] candidates not found")


def write_import_error(output: CommandOutput, *, detail_id: str, message: str) -> None:
    output.write_warning(f"[applicability-error] detail_id={detail_id} message={message}")


def write_progress(output: CommandOutput, *, processed: int, total: int, detail_id: str) -> None:
    if processed <= 5 or processed % 100 == 0 or processed == total:
        output.write(f"[progress] {processed}/{total} detail_id={detail_id}")
