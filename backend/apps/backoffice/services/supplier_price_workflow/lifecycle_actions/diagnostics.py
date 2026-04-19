from __future__ import annotations

from apps.backoffice.selectors import get_supplier_source_by_code
from apps.supplier_imports.selectors import get_supplier_integration_by_code

from ..diagnostics import get_price_list
from ..serialization import serialize_price_list


def resolve_source_and_integration(*, supplier_code: str):
    source = get_supplier_source_by_code(supplier_code=supplier_code)
    integration = get_supplier_integration_by_code(source_code=supplier_code)
    return source, integration


def get_price_list_for_source(*, price_list_id: str, source_id: str):
    return get_price_list(price_list_id=price_list_id, source_id=source_id)


def serialize_with_cooldown(service, *, integration, row) -> dict:
    cooldown = service.guard.get_status(integration=integration)
    return serialize_price_list(row=row, cooldown_wait_seconds=cooldown.wait_seconds)
