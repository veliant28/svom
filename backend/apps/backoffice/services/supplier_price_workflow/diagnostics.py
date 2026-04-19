from __future__ import annotations

from apps.supplier_imports.models import SupplierPriceList
from apps.supplier_imports.services.integrations.exceptions import SupplierIntegrationError


def get_price_list(*, price_list_id: str, source_id: str) -> SupplierPriceList:
    try:
        return SupplierPriceList.objects.select_related("imported_run").get(id=price_list_id, source_id=source_id)
    except SupplierPriceList.DoesNotExist as exc:
        raise SupplierIntegrationError("Прайс не найден.") from exc
