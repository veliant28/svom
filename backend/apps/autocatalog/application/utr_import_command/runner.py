from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.conf import settings
from django.utils.translation import gettext as _

from apps.autocatalog.services.utr_run_lock_service import UtrRunLockService

from . import modes, observability
from .types import CommandOutput


def run_utr_import_command(*, raw_options: Mapping[str, Any], output: CommandOutput) -> None:
    if not observability.is_utr_enabled():
        output.write_warning(_("UTR отключен через UTR_ENABLED=0. Пропуск выполнения."))
        return

    observability.reset_process_metrics()
    run_counters = observability.empty_run_counters()

    force_refresh = observability.resolve_force_refresh(raw_options)
    if force_refresh and not observability.is_unsafe_force_refresh_enabled():
        run_counters["skipped_due_to_force_refresh_protection"] += 1
        output.write_warning(
            _(
                "UTR force refresh заблокирован: задайте UTR_FORCE_REFRESH=1 и "
                "UTR_UNSAFE_ALLOW_FORCE_REFRESH=1 одновременно."
            )
        )
        output.write("[utr-guard] skipped_due_to_force_refresh_protection=1")
        observability.write_observability(output, run_counters=run_counters)
        return

    lock_service = UtrRunLockService(
        lock_key=int(getattr(settings, "UTR_SINGLE_RUN_LOCK_KEY", 804721451)),
        cache_ttl_seconds=int(getattr(settings, "UTR_SINGLE_RUN_LOCK_TTL_SECONDS", 60 * 60)),
    )

    try:
        with lock_service.hold() as acquired:
            if not acquired:
                run_counters["skipped_due_to_existing_lock"] += 1
                output.write_warning(_("UTR import уже выполняется в другом процессе. Текущий запуск пропущен."))
                output.write("[utr-lock] skipped_due_to_existing_lock=1")
                return

            modes.run_autocatalog_import_flow(
                raw_options=raw_options,
                force_refresh=force_refresh,
                output=output,
            )
    finally:
        observability.write_observability(output, run_counters=run_counters)
