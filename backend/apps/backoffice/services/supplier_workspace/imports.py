from __future__ import annotations

from pathlib import Path

from apps.backoffice.selectors import get_supplier_source_by_code
from apps.supplier_imports.parsers import ParserContext, UTRParser
from apps.supplier_imports.parsers.utils import parse_table_rows, parse_xlsx_rows, rows_to_csv_content
from apps.supplier_imports.selectors import get_supplier_integration_by_code
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError, SupplierIntegrationError
from apps.supplier_imports.services.mapped_offer_publish_service import SupplierMappedOffersPublishService

from . import diagnostics, serialization, workspace


def run_import(service, *, supplier_code: str, dry_run: bool = False, dispatch_async: bool = False) -> dict:
    integration = get_supplier_integration_by_code(source_code=supplier_code)
    if not integration.is_enabled:
        raise SupplierIntegrationError("Интеграция поставщика отключена.")

    result = service.import_orchestration.run_import(
        source_code=supplier_code,
        dry_run=dry_run,
        dispatch_async=dispatch_async,
        trigger="backoffice:supplier_workspace_import",
    )
    return serialization.serialize_orchestration_result(result=result)


def sync_prices(service, *, supplier_code: str, dispatch_async: bool = False) -> dict:
    integration = get_supplier_integration_by_code(source_code=supplier_code)
    if not integration.is_enabled:
        raise SupplierIntegrationError("Интеграция поставщика отключена.")

    result = service.import_orchestration.sync_prices(source_code=supplier_code, dispatch_async=dispatch_async)
    return serialization.serialize_orchestration_result(result=result)


def import_utr_brands(service) -> dict:
    supplier_code = "utr"
    integration = get_supplier_integration_by_code(source_code=supplier_code)
    service._guard_and_validate_enabled(integration=integration, action_key="utr_brands_import")

    try:
        rows, import_source = fetch_utr_brand_rows(service, integration=integration, supplier_code=supplier_code)
        summary = service.utr_brand_import.import_rows(rows=rows, source_code=supplier_code)
        imported_count = summary.created + summary.updated
        service.integration_state.mark_brands_import_success(
            integration=integration,
            imported_count=imported_count,
        )
    except Exception as exc:
        diagnostics.log_brands_import_failure(supplier_code=supplier_code, exc=exc)
        service.integration_state.mark_brands_import_failure(integration=integration, message=str(exc))
        raise SupplierIntegrationError("Не удалось сохранить бренды UTR.") from exc

    return serialization.serialize_utr_brands_import_result(
        imported_count=imported_count,
        source=import_source,
        summary=summary,
        workspace_payload=workspace.get_workspace(service, supplier_code=supplier_code),
    )


def publish_mapped_products(
    service,
    *,
    supplier_code: str,
    include_needs_review: bool = False,
    dry_run: bool = False,
    reprice_after_publish: bool = True,
) -> dict:
    # Ensure supplier/source exists and is supported by workspace.
    get_supplier_source_by_code(supplier_code=supplier_code)
    result = SupplierMappedOffersPublishService().publish_for_supplier(
        supplier_code=supplier_code,
        include_needs_review=include_needs_review,
        dry_run=dry_run,
        reprice_after_publish=reprice_after_publish,
    )
    return serialization.serialize_publish_mapped_result(result=result)


def fetch_utr_brand_rows(service, *, integration, supplier_code: str) -> tuple[list[dict], str]:
    if integration.access_token:
        try:
            return service.utr_client.fetch_brands(access_token=integration.access_token), "utr_api"
        except SupplierClientError:
            # Fallback to local UTR source file when API token is invalid/expired.
            pass

    source = get_supplier_source_by_code(supplier_code=supplier_code)
    file_path = Path(source.input_path).expanduser()
    if not file_path.exists() or not file_path.is_file():
        raise SupplierIntegrationError("Нет access token и отсутствует доступный UTR-файл для импорта брендов.")

    if file_path.suffix.lower() == ".xlsx":
        rows = parse_xlsx_rows(file_path)
        content = rows_to_csv_content(rows)
    else:
        content = file_path.read_text(encoding="utf-8", errors="ignore")

    parser = UTRParser()
    parse_result = parser.parse_content(
        content,
        file_name=file_path.name,
        context=ParserContext(
            source_code=source.code,
            mapping_config=source.mapping_config,
            default_currency=source.default_currency,
        ),
    )

    brands = [{"name": offer.brand_name} for offer in parse_result.offers if offer.brand_name.strip()]
    if brands:
        return brands, "utr_file"

    # Secondary extraction for edge-case files that parser cannot map to ParsedOffer.
    fallback_rows = parse_table_rows(content)
    extracted: list[dict] = []
    for _, row in fallback_rows:
        brand_name = (
            row.get("Бренд")
            or row.get("бренд")
            or row.get("brand")
            or row.get("Brand")
            or row.get("displayBrand")
            or row.get("brand_name")
            or ""
        ).strip()
        if brand_name:
            extracted.append({"name": brand_name})

    if not extracted:
        raise SupplierIntegrationError("UTR-файл не содержит брендов для импорта.")
    return extracted, "utr_file"
