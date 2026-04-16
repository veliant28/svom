from __future__ import annotations

from dataclasses import dataclass

from apps.supplier_imports.selectors import ensure_default_import_sources, get_import_source_by_code
from apps.supplier_imports.services.import_runner import SupplierImportRunner
from apps.supplier_imports.tasks import import_supplier_file_task


@dataclass(frozen=True)
class ImportOrchestrationResult:
    mode: str
    payload: dict


class SupplierImportOrchestrationService:
    def run_import(
        self,
        *,
        source_code: str,
        dry_run: bool = False,
        dispatch_async: bool = False,
        reprice: bool | None = None,
        reindex: bool | None = None,
        trigger: str = "backoffice:supplier_workspace_import",
    ) -> ImportOrchestrationResult:
        ensure_default_import_sources()
        source = get_import_source_by_code(source_code)

        if dispatch_async:
            task = import_supplier_file_task.delay(
                source_code=source.code,
                dry_run=dry_run,
                reprice=reprice,
                reindex=reindex,
                trigger=trigger,
            )
            return ImportOrchestrationResult(
                mode="async",
                payload={
                    "task_id": task.id,
                    "source_code": source.code,
                    "dry_run": dry_run,
                },
            )

        result = SupplierImportRunner().run_source(
            source=source,
            dry_run=dry_run,
            trigger=trigger,
            reprice=reprice,
            reindex=reindex,
        )
        return ImportOrchestrationResult(
            mode="sync",
            payload={
                "run_id": result.run_id,
                "source_code": result.source_code,
                "status": result.status,
                "result": result.summary,
                "dry_run": dry_run,
            },
        )

    def sync_prices(
        self,
        *,
        source_code: str,
        dispatch_async: bool = False,
    ) -> ImportOrchestrationResult:
        return self.run_import(
            source_code=source_code,
            dry_run=False,
            dispatch_async=dispatch_async,
            trigger="backoffice:supplier_workspace_prices_sync",
            reprice=True,
            reindex=False,
        )
