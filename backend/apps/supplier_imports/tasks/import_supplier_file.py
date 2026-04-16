from celery import shared_task

from apps.supplier_imports.selectors import ensure_default_import_sources, get_import_source_by_code
from apps.supplier_imports.services import SupplierImportRunner
from apps.supplier_imports.services.integrations.exceptions import SupplierCooldownError


@shared_task(name="supplier_imports.import_supplier_file")
def import_supplier_file_task(
    source_code: str,
    *,
    dry_run: bool = False,
    trigger: str = "task:import_supplier_file",
    file_paths: list[str] | None = None,
    reprice: bool | None = None,
    reindex: bool | None = None,
) -> dict:
    ensure_default_import_sources()
    source = get_import_source_by_code(source_code)
    try:
        result = SupplierImportRunner().run_source(
            source=source,
            trigger=trigger,
            dry_run=dry_run,
            file_paths=file_paths,
            reprice=reprice,
            reindex=reindex,
        )
    except SupplierCooldownError as exc:
        return {
            "source": source_code,
            "status": "blocked_by_cooldown",
            "detail": str(exc),
            "retry_after_seconds": exc.retry_after_seconds,
        }
    return {
        "run_id": result.run_id,
        "source": result.source_code,
        "status": result.status,
        "summary": result.summary,
    }
