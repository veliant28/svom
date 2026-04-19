from __future__ import annotations

from apps.backoffice.selectors import (
    get_supplier_errors_queryset,
    get_supplier_runs_queryset,
    get_supplier_source_by_code,
    get_supplier_workspace_sources_queryset,
)
from apps.supplier_imports.selectors import get_supplier_integration_by_code

from . import serialization


def list_suppliers(service) -> list[dict]:
    rows: list[dict] = []
    for source in get_supplier_workspace_sources_queryset():
        integration = get_supplier_integration_by_code(source_code=source.code)
        cooldown = service.guard.get_status(integration=integration)
        rows.append(
            serialization.serialize_supplier_row(
                source=source,
                integration=integration,
                cooldown=cooldown,
            )
        )
    return rows


def get_workspace(service, *, supplier_code: str) -> dict:
    source = get_supplier_source_by_code(supplier_code=supplier_code)
    integration = get_supplier_integration_by_code(source_code=supplier_code)
    latest_run = get_supplier_runs_queryset(supplier_code=supplier_code).first()
    latest_error = get_supplier_errors_queryset(supplier_code=supplier_code).first()
    cooldown = service.guard.get_status(integration=integration)

    return serialization.serialize_workspace_payload(
        source=source,
        integration=integration,
        latest_run=latest_run,
        latest_error=latest_error,
        cooldown=cooldown,
    )


def get_cooldown(service, *, supplier_code: str) -> dict:
    integration = get_supplier_integration_by_code(source_code=supplier_code)
    cooldown = service.guard.get_status(integration=integration)
    return serialization.serialize_cooldown_payload(supplier_code=supplier_code, cooldown=cooldown)
