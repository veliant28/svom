from __future__ import annotations

from dataclasses import dataclass

from apps.supplier_imports.models import ImportRun
from apps.supplier_imports.selectors import ensure_default_import_sources, get_active_import_sources, get_import_source_by_code
from apps.supplier_imports.services import SupplierImportRunner
from apps.supplier_imports.services.integrations.exceptions import SupplierCooldownError
from apps.supplier_imports.tasks import import_all_suppliers_task, import_supplier_file_task, reprice_after_import_task


@dataclass(frozen=True)
class ActionResult:
    mode: str
    payload: dict


class ImportActionsService:
    def run_source(
        self,
        *,
        source_code: str,
        dry_run: bool,
        dispatch_async: bool,
        reprice: bool | None,
        reindex: bool | None,
        file_paths: list[str] | None,
        trigger: str,
    ) -> ActionResult:
        ensure_default_import_sources()

        if dispatch_async:
            task = import_supplier_file_task.delay(
                source_code=source_code,
                dry_run=dry_run,
                reprice=reprice,
                reindex=reindex,
                file_paths=file_paths,
                trigger=trigger,
            )
            return ActionResult(
                mode="async",
                payload={
                    "task_id": task.id,
                    "source_code": source_code,
                    "dry_run": dry_run,
                },
            )

        source = get_import_source_by_code(source_code)
        result = SupplierImportRunner().run_source(
            source=source,
            dry_run=dry_run,
            reprice=reprice,
            reindex=reindex,
            file_paths=file_paths,
            trigger=trigger,
        )

        return ActionResult(mode="sync", payload={"result": result.summary, "run_id": result.run_id, "status": result.status})

    def run_all(
        self,
        *,
        dry_run: bool,
        dispatch_async: bool,
        reprice: bool | None,
        reindex: bool | None,
        trigger: str,
    ) -> ActionResult:
        ensure_default_import_sources()

        if dispatch_async:
            task = import_all_suppliers_task.delay(
                dry_run=dry_run,
                reprice=reprice,
                reindex=reindex,
                trigger=trigger,
            )
            return ActionResult(mode="async", payload={"task_id": task.id, "dry_run": dry_run})

        results = []
        for source in get_active_import_sources():
            try:
                run_result = SupplierImportRunner().run_source(
                    source=source,
                    dry_run=dry_run,
                    reprice=reprice,
                    reindex=reindex,
                    trigger=trigger,
                )
                results.append(
                    {
                        "source": run_result.source_code,
                        "run_id": run_result.run_id,
                        "status": run_result.status,
                        "summary": run_result.summary,
                    }
                )
            except SupplierCooldownError as exc:
                results.append(
                    {
                        "source": source.code,
                        "status": "blocked_by_cooldown",
                        "detail": str(exc),
                        "retry_after_seconds": exc.retry_after_seconds,
                    }
                )

        return ActionResult(mode="sync", payload={"sources": len(results), "results": results})

    def reprice_after_import(self, *, run_id: str, dispatch_async: bool, trigger: str) -> ActionResult:
        run = ImportRun.objects.select_related("source").get(id=run_id)

        if dispatch_async:
            task = reprice_after_import_task.delay(import_run_id=str(run.id), trigger_note=trigger)
            return ActionResult(mode="async", payload={"task_id": task.id, "run_id": str(run.id)})

        stats = reprice_after_import_task(import_run_id=str(run.id), trigger_note=trigger)
        return ActionResult(mode="sync", payload={"run_id": str(run.id), "stats": stats})
