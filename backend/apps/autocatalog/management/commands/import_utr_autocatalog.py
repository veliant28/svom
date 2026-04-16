from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _

from apps.autocatalog.services import (
    AutocatalogImportSummary,
    UtrArticleDetailResolverService,
    UtrArticleResolveProgress,
    UtrArticleResolveSummary,
    UtrAutocatalogImportService,
)
from apps.autocatalog.services.utr_run_lock_service import UtrRunLockService
from apps.catalog.models import Product
from apps.supplier_imports.selectors import get_supplier_integration_by_code
from apps.supplier_imports.services.integrations.utr_client import UtrClient


class Command(BaseCommand):
    help = _("Импортирует автокаталог из UTR applicability по detail_id из Product и/или UTR article.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help=_("Ограничить количество utr_detail_id для обработки."),
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=0,
            help=_("Смещение по списку utr_detail_id для батчевого запуска."),
        )
        parser.add_argument(
            "--resolve-utr-articles",
            action="store_true",
            help=_("Сначала получить detail_id через UTR search по артикулу UTR из сырых офферов."),
        )
        parser.add_argument(
            "--resolve-limit",
            type=int,
            default=None,
            help=_("Ограничить количество пар артикул+бренд для резолва detail_id."),
        )
        parser.add_argument(
            "--resolve-offset",
            type=int,
            default=0,
            help=_("Смещение по парам артикул+бренд для резолва detail_id."),
        )
        parser.add_argument(
            "--resolve-until-empty",
            action="store_true",
            help=_("Крутить резолв батчами до исчерпания кандидатов."),
        )
        parser.add_argument(
            "--retry-unresolved",
            action="store_true",
            help=_("Резолвить пары, у которых уже есть mapping c пустым utr_detail_id."),
        )
        parser.add_argument(
            "--resolve-only",
            action="store_true",
            help=_("Выполнить только резолв article->detail, без импорта applicability."),
        )
        parser.add_argument(
            "--products-only",
            action="store_true",
            help=_("Брать detail_id только из Product.utr_detail_id, без резолва по артикулам."),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help=_("Размер батча detail_id за один внутренний проход."),
        )
        parser.add_argument(
            "--force-refresh",
            action="store_true",
            help=_("Игнорировать кеш и существующие mapping-и, принудительно дергать UTR."),
        )

    def handle(self, *args, **options):
        if not bool(getattr(settings, "UTR_ENABLED", True)):
            self.stdout.write(self.style.WARNING(_("UTR отключен через UTR_ENABLED=0. Пропуск выполнения.")))
            return

        UtrClient.reset_process_metrics()
        run_counters = {
            "skipped_due_to_existing_lock": 0,
            "skipped_due_to_force_refresh_protection": 0,
        }

        force_refresh = bool(options.get("force_refresh") or getattr(settings, "UTR_FORCE_REFRESH", False))
        unsafe_force_refresh = bool(getattr(settings, "UTR_UNSAFE_ALLOW_FORCE_REFRESH", False))
        if force_refresh and not unsafe_force_refresh:
            run_counters["skipped_due_to_force_refresh_protection"] += 1
            self.stdout.write(
                self.style.WARNING(
                    _(
                        "UTR force refresh заблокирован: задайте UTR_FORCE_REFRESH=1 и "
                        "UTR_UNSAFE_ALLOW_FORCE_REFRESH=1 одновременно."
                    )
                )
            )
            self.stdout.write("[utr-guard] skipped_due_to_force_refresh_protection=1")
            self._print_observability(run_counters=run_counters)
            return

        lock_service = UtrRunLockService(
            lock_key=int(getattr(settings, "UTR_SINGLE_RUN_LOCK_KEY", 804721451)),
            cache_ttl_seconds=int(getattr(settings, "UTR_SINGLE_RUN_LOCK_TTL_SECONDS", 60 * 60)),
        )

        try:
            with lock_service.hold() as acquired:
                if not acquired:
                    run_counters["skipped_due_to_existing_lock"] += 1
                    self.stdout.write(
                        self.style.WARNING(_("UTR import уже выполняется в другом процессе. Текущий запуск пропущен."))
                    )
                    self.stdout.write("[utr-lock] skipped_due_to_existing_lock=1")
                    return
                self._run_import(options=options, force_refresh=force_refresh)
        finally:
            self._print_observability(run_counters=run_counters)

    def _run_import(self, *, options, force_refresh: bool) -> None:
        integration = get_supplier_integration_by_code(source_code="utr")
        if not integration.access_token:
            raise CommandError(_("UTR access token отсутствует. Сначала обновите токен интеграции UTR."))

        limit = options.get("limit")
        offset = max(0, int(options.get("offset") or 0))
        resolve_until_empty = bool(options.get("resolve_until_empty"))
        retry_unresolved = bool(options.get("retry_unresolved"))
        resolve_only = bool(options.get("resolve_only"))
        resolve_utr_articles = bool(
            options.get("resolve_utr_articles") or resolve_until_empty or retry_unresolved or resolve_only
        )
        products_only = bool(options.get("products_only"))
        resolve_limit = options.get("resolve_limit")
        resolve_offset = max(0, int(options.get("resolve_offset") or 0))
        batch_size = options.get("batch_size")
        if not batch_size or int(batch_size) <= 0:
            batch_size = int(getattr(settings, "UTR_BATCH_SIZE", 25))
        batch_size = max(int(batch_size), 1)
        resolver = UtrArticleDetailResolverService()

        if products_only and (resolve_utr_articles or resolve_until_empty or retry_unresolved or resolve_only):
            raise CommandError(_("--products-only нельзя комбинировать с resolve-опциями."))
        if resolve_until_empty and retry_unresolved:
            raise CommandError(_("--resolve-until-empty и --retry-unresolved используйте отдельными запусками."))
        if resolve_until_empty and resolve_offset > 0 and not retry_unresolved:
            raise CommandError(_("--resolve-until-empty используйте без --resolve-offset (для нового прохода offset не нужен)."))

        product_detail_ids = self._collect_product_detail_ids()
        self.stdout.write(f"Product detail ids available: {len(product_detail_ids)}")

        mapped_detail_ids: list[str] = [] if products_only else resolver.collect_detail_ids()
        if not products_only:
            self.stdout.write(f"Resolved article->detail mappings in DB: {len(mapped_detail_ids)}")

        should_run_resolve = not products_only and (
            resolve_utr_articles or not product_detail_ids and not mapped_detail_ids
        )
        if should_run_resolve:
            self.stdout.write(_("Запуск резолва UTR detail_id по артикулу UTR..."))
            self.stdout.write(
                f"[resolve-runtime] resolve_batch_size={getattr(settings, 'UTR_RESOLVE_BATCH_SIZE', 10)} "
                f"resolve_stage_order={getattr(settings, 'UTR_RESOLVE_STAGE_ORDER', 'branded_first')} "
                f"rate_limit_per_minute={getattr(settings, 'UTR_RATE_LIMIT_PER_MINUTE', 6)} "
                f"concurrency={getattr(settings, 'UTR_CONCURRENCY', 1)}"
            )
            self._print_resolve_progress(label="before", progress=resolver.collect_progress())
            resolve_summary = self._run_resolve(
                resolver=resolver,
                access_token=integration.access_token,
                resolve_limit=resolve_limit,
                resolve_offset=resolve_offset,
                resolve_until_empty=resolve_until_empty,
                retry_unresolved=retry_unresolved,
            )
            self.stdout.write("[resolve-summary]")
            for key, value in resolve_summary.to_dict().items():
                self.stdout.write(f"  - {key}: {value}")
            self._print_resolve_progress(label="after", progress=resolver.collect_progress())

            if resolve_summary.stopped_due_to_circuit_breaker > 0:
                self.stdout.write(
                    self.style.WARNING(
                        _(
                            "UTR circuit breaker открыт во время resolve-фазы. "
                            "Импорт остановлен до нового безопасного запуска после cooldown."
                        )
                    )
                )
                self.stdout.write("[utr-stop] circuit_breaker_open=1 phase=resolve")
                return

            mapped_detail_ids = resolver.collect_detail_ids()
            self.stdout.write(f"Resolved article->detail mappings in DB: {len(mapped_detail_ids)}")
            # Access token may be refreshed/re-obtained inside batch resolve flow.
            integration = get_supplier_integration_by_code(source_code="utr")

        if resolve_only:
            self.stdout.write(self.style.SUCCESS(_("Резолв article->detail завершен (режим --resolve-only).")))
            return

        detail_ids = self._merge_detail_ids(product_detail_ids, mapped_detail_ids, limit=limit, offset=offset)
        if not detail_ids:
            self.stdout.write(
                self.style.WARNING(
                    _("Не найдено utr_detail_id. Запустите с --resolve-utr-articles для резолва по артикулу UTR.")
                )
            )
            return

        self.stdout.write(f"Detail ids to process: {len(detail_ids)} (offset={offset}, limit={limit or 'all'})")
        self.stdout.write(
            f"[utr-runtime] rate_limit_per_minute={getattr(settings, 'UTR_RATE_LIMIT_PER_MINUTE', 6)} "
            f"concurrency={getattr(settings, 'UTR_CONCURRENCY', 1)} "
            f"batch_size={batch_size} "
            f"applicability_enabled={int(bool(getattr(settings, 'UTR_APPLICABILITY_ENABLED', True)))} "
            f"force_refresh={int(force_refresh)} "
            f"unsafe_force_refresh={int(bool(getattr(settings, 'UTR_UNSAFE_ALLOW_FORCE_REFRESH', False)))}"
        )
        service = UtrAutocatalogImportService()
        summary = AutocatalogImportSummary()
        total_detail_ids = len(detail_ids)

        for chunk_index, start in enumerate(range(0, total_detail_ids, batch_size), start=1):
            chunk = detail_ids[start : start + batch_size]
            self.stdout.write(f"[chunk {chunk_index}] start={start} size={len(chunk)}")

            def _chunk_progress(processed: int, _chunk_total: int, detail_id: str, *, base_offset: int = start) -> None:
                self._log_progress(base_offset + processed, total_detail_ids, detail_id)

            batch_summary = service.import_from_detail_ids(
                detail_ids=chunk,
                access_token=integration.access_token,
                on_error=self._log_import_error,
                on_progress=_chunk_progress,
                continue_on_error=True,
                force_refresh=force_refresh,
            )
            self._accumulate_import_summary(total=summary, batch=batch_summary)

            if batch_summary.stopped_due_to_circuit_breaker > 0:
                self.stdout.write(
                    self.style.WARNING(
                        _(
                            "UTR circuit breaker открыт во время applicability-фазы. "
                            "Дальнейшие запросы остановлены до нового запуска после cooldown."
                        )
                    )
                )
                self.stdout.write("[utr-stop] circuit_breaker_open=1 phase=applicability")
                break

        if summary.stopped_due_to_circuit_breaker > 0:
            self.stdout.write(self.style.WARNING(_("Импорт автокаталога остановлен circuit breaker.")))
        else:
            self.stdout.write(self.style.SUCCESS(_("Импорт автокаталога завершен.")))
        for key, value in summary.to_dict().items():
            self.stdout.write(f"  - {key}: {value}")

    def _collect_product_detail_ids(self) -> list[str]:
        queryset = (
            Product.objects.exclude(utr_detail_id__isnull=True)
            .exclude(utr_detail_id="")
            .values_list("utr_detail_id", flat=True)
            .distinct()
            .order_by("utr_detail_id")
        )
        return [value for value in queryset if str(value).isdigit()]

    def _merge_detail_ids(
        self,
        product_detail_ids: list[str],
        mapped_detail_ids: list[str],
        *,
        limit: int | None,
        offset: int,
    ) -> list[str]:
        merged = sorted({*product_detail_ids, *mapped_detail_ids}, key=int)
        if offset > 0:
            merged = merged[offset:]
        if limit and limit > 0:
            merged = merged[:limit]
        return merged

    def _log_resolve_error(self, pair: dict, message: str) -> None:
        article = pair.get("article") or ""
        brand = pair.get("brand_name") or ""
        self.stdout.write(self.style.WARNING(f"[resolve-error] article={article} brand={brand} message={message}"))

    def _log_resolve_search_batch(self, event: dict) -> None:
        stage = str(event.get("stage") or "")
        batch_index = int(event.get("batch_index") or 0)
        batch_size = int(event.get("batch_size") or 0)
        if bool(event.get("failed")):
            message = str(event.get("message") or "")
            failure_kind = str(event.get("failure_kind") or "")
            self.stdout.write(
                self.style.WARNING(
                    f"[resolve-search-batch] stage={stage} batch={batch_index} size={batch_size} "
                    f"failed=1 failure_kind={failure_kind} message={message}"
                )
            )
            return
        if bool(event.get("auth_retry")):
            auth_method = str(event.get("auth_method") or "")
            saved_pairs = int(event.get("saved_pairs") or 0)
            self.stdout.write(
                f"[resolve-search-batch] stage={stage} batch={batch_index} size={batch_size} "
                f"auth_retry=1 method={auth_method} saved_pairs={saved_pairs}"
            )
        details_non_empty = int(event.get("details_non_empty") or 0)
        errors_in_batch = int(event.get("errors_in_batch") or 0)
        auth_errors = int(event.get("auth_errors") or 0)
        self.stdout.write(
            f"[resolve-search-batch] stage={stage} batch={batch_index} size={batch_size} "
            f"details_non_empty={details_non_empty} errors={errors_in_batch} auth_errors={auth_errors}"
        )

    def _log_import_error(self, detail_id: str, message: str) -> None:
        self.stdout.write(self.style.WARNING(f"[applicability-error] detail_id={detail_id} message={message}"))

    def _log_progress(self, processed: int, total: int, detail_id: str) -> None:
        if processed <= 5 or processed % 100 == 0 or processed == total:
            self.stdout.write(f"[progress] {processed}/{total} detail_id={detail_id}")

    def _run_resolve(
        self,
        *,
        resolver: UtrArticleDetailResolverService,
        access_token: str,
        resolve_limit: int | None,
        resolve_offset: int,
        resolve_until_empty: bool,
        retry_unresolved: bool,
    ) -> UtrArticleResolveSummary:
        batch_limit = resolve_limit if resolve_limit and resolve_limit > 0 else max(int(getattr(settings, "UTR_BATCH_SIZE", 25)), 1)
        total = UtrArticleResolveSummary()
        batch_index = 0
        batch_offset = resolve_offset

        while True:
            batch_index += 1
            summary = resolver.resolve_from_raw_offers(
                access_token=access_token,
                limit=batch_limit,
                offset=batch_offset,
                retry_unresolved=retry_unresolved,
                on_error=self._log_resolve_error,
                on_batch=self._log_resolve_search_batch,
            )
            if summary.article_pairs_total == 0:
                if batch_index == 1:
                    self.stdout.write("[resolve-batch] candidates not found")
                break

            self.stdout.write(
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
            self._accumulate_resolve_summary(total=total, batch=summary)

            if not resolve_until_empty:
                break
            if summary.article_pairs_total < batch_limit:
                break

            batch_offset = 0

        return total

    def _accumulate_resolve_summary(
        self,
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

    def _accumulate_import_summary(
        self,
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

    def _print_resolve_progress(self, *, label: str, progress: UtrArticleResolveProgress) -> None:
        self.stdout.write(f"[resolve-progress:{label}]")
        for key, value in progress.to_dict().items():
            self.stdout.write(f"  - {key}: {value}")

    def _print_observability(self, *, run_counters: dict[str, int]) -> None:
        self.stdout.write("[utr-observability]")
        metrics = UtrClient.get_process_metrics()
        for key in (
            "requests_sent_total",
            "requests_skipped_cache",
            "retries_total",
            "timeouts_total",
            "http_429_total",
            "http_5xx_total",
            "circuit_breaker_open_total",
            "auth_refresh_total",
            "auth_relogin_total",
            "auth_retry_batch_total",
        ):
            self.stdout.write(f"  - {key}: {int(metrics.get(key, 0))}")
        self.stdout.write(f"  - skipped_due_to_existing_lock: {int(run_counters.get('skipped_due_to_existing_lock', 0))}")
        self.stdout.write(
            "  - skipped_due_to_force_refresh_protection: "
            f"{int(run_counters.get('skipped_due_to_force_refresh_protection', 0))}"
        )
