from celery import shared_task

from apps.supplier_imports.selectors import ensure_default_import_sources, get_active_import_sources
from apps.supplier_imports.services import SupplierImportRunner


@shared_task(name="supplier_imports.import_all_suppliers")
def import_all_suppliers_task(
    *,
    dry_run: bool = False,
    trigger: str = "task:import_all_suppliers",
    reprice: bool | None = None,
    reindex: bool | None = None,
) -> dict:
    ensure_default_import_sources()

    results: list[dict] = []
    for source in get_active_import_sources():
        run_result = SupplierImportRunner().run_source(
            source=source,
            dry_run=dry_run,
            trigger=trigger,
            reprice=reprice,
            reindex=reindex,
        )
        results.append(
            {
                "run_id": run_result.run_id,
                "source": run_result.source_code,
                "status": run_result.status,
                "summary": run_result.summary,
            }
        )

    return {
        "sources": len(results),
        "results": results,
    }
