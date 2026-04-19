from __future__ import annotations

import json
import logging
import socket
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .constants import DEFAULT_TIMEOUT_SECONDS, LOOKUP_TIMEOUT_SECONDS, NOVA_POSHTA_API_URL, NOVA_POSHTA_PRINT_BASE_URL
from .error_mapper import map_error_from_payload
from .errors import NovaPoshtaErrorContext, NovaPoshtaIntegrationError
from .normalizers import extract_error_context

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NovaPoshtaResponse:
    payload: dict[str, Any]
    context: NovaPoshtaErrorContext


class NovaPoshtaApiClient:
    def __init__(self, *, api_token: str):
        self.api_token = (api_token or "").strip()
        if not self.api_token:
            raise NovaPoshtaIntegrationError("Не задан API токен Новой Почты.")

    def search_settlements(self, *, query: str, limit: int = 20, page: int = 1) -> NovaPoshtaResponse:
        return self._request(
            model_name="AddressGeneral",
            called_method="searchSettlements",
            method_properties={
                "CityName": query,
                "Limit": str(max(1, min(limit, 50))),
                "Page": str(max(1, page)),
            },
            timeout=LOOKUP_TIMEOUT_SECONDS,
            safe_to_retry=True,
            operation="online settlements search",
        )

    def search_streets(self, *, settlement_ref: str, query: str, limit: int = 20) -> NovaPoshtaResponse:
        return self._request(
            model_name="AddressGeneral",
            called_method="searchSettlementStreets",
            method_properties={
                "SettlementRef": settlement_ref,
                "StreetName": query,
                "Limit": str(max(1, min(limit, 50))),
            },
            timeout=LOOKUP_TIMEOUT_SECONDS,
            safe_to_retry=True,
            operation="online streets search",
        )

    def get_cities(self, *, query: str = "", limit: int = 50, page: int = 1, ref: str = "") -> NovaPoshtaResponse:
        method_properties: dict[str, Any] = {
            "Page": str(max(1, page)),
            "Limit": str(max(1, min(limit, 200))),
        }
        normalized_query = query.strip()
        if normalized_query:
            method_properties["FindByString"] = normalized_query
        normalized_ref = ref.strip()
        if normalized_ref:
            method_properties["Ref"] = normalized_ref

        return self._request(
            model_name="AddressGeneral",
            called_method="getCities",
            method_properties=method_properties,
            timeout=LOOKUP_TIMEOUT_SECONDS,
            safe_to_retry=True,
            operation="cities lookup",
        )

    def get_warehouses(
        self,
        *,
        city_ref: str = "",
        query: str = "",
        warehouse_type_ref: str | None = None,
        language: str = "UA",
        limit: int = 50,
        page: int = 1,
    ) -> NovaPoshtaResponse:
        properties: dict[str, Any] = {
            "FindByString": query,
            "Limit": str(max(1, min(limit, 200))),
            "Page": str(max(1, page)),
            "Language": language.upper() if language else "UA",
        }
        normalized_city_ref = city_ref.strip()
        if normalized_city_ref:
            properties["CityRef"] = normalized_city_ref
        if warehouse_type_ref:
            properties["TypeOfWarehouseRef"] = warehouse_type_ref

        return self._request(
            model_name="AddressGeneral",
            called_method="getWarehouses",
            method_properties=properties,
            timeout=LOOKUP_TIMEOUT_SECONDS,
            safe_to_retry=True,
            operation="warehouses lookup",
        )

    def get_pack_list_special(
        self,
        *,
        length_mm: int,
        width_mm: int,
        height_mm: int,
        pack_for_sale: str = "1",
    ) -> NovaPoshtaResponse:
        return self._request(
            model_name="Common",
            called_method="getPackListSpecial",
            method_properties={
                "Length": int(max(1, length_mm)),
                "Width": int(max(1, width_mm)),
                "Height": int(max(1, height_mm)),
                "PackForSale": pack_for_sale or "1",
            },
            timeout=LOOKUP_TIMEOUT_SECONDS,
            safe_to_retry=True,
            operation="pack list special lookup",
        )

    def get_pack_list(self, *, pack_for_sale: str = "1") -> NovaPoshtaResponse:
        method_properties: dict[str, Any] = {}
        normalized_pack_for_sale = (pack_for_sale or "").strip()
        if normalized_pack_for_sale:
            method_properties["PackForSale"] = normalized_pack_for_sale
        return self._request(
            model_name="Common",
            called_method="getPackList",
            method_properties=method_properties,
            timeout=LOOKUP_TIMEOUT_SECONDS,
            safe_to_retry=True,
            operation="pack list lookup",
        )

    def get_time_intervals(
        self,
        *,
        recipient_city_ref: str,
        date_time: str = "",
    ) -> NovaPoshtaResponse:
        method_properties: dict[str, Any] = {"RecipientCityRef": recipient_city_ref.strip()}
        normalized_date_time = date_time.strip()
        if normalized_date_time:
            method_properties["DateTime"] = normalized_date_time
        return self._request(
            model_name="CommonGeneral",
            called_method="getTimeIntervals",
            method_properties=method_properties,
            timeout=LOOKUP_TIMEOUT_SECONDS,
            safe_to_retry=True,
            operation="time intervals lookup",
        )

    def get_document_delivery_date(
        self,
        *,
        date_time: str,
        service_type: str,
        city_sender: str,
        city_recipient: str,
    ) -> NovaPoshtaResponse:
        method_properties: dict[str, Any] = {
            "DateTime": date_time.strip(),
            "ServiceType": service_type.strip(),
            "CitySender": city_sender.strip(),
            "CityRecipient": city_recipient.strip(),
        }
        return self._request(
            model_name="InternetDocumentGeneral",
            called_method="getDocumentDeliveryDate",
            method_properties=method_properties,
            timeout=LOOKUP_TIMEOUT_SECONDS,
            safe_to_retry=True,
            operation="delivery date lookup",
        )

    def get_counterparty_options(self, *, counterparty_ref: str) -> NovaPoshtaResponse:
        return self._request(
            model_name="CounterpartyGeneral",
            called_method="getCounterpartyOptions",
            method_properties={"Ref": counterparty_ref},
            timeout=DEFAULT_TIMEOUT_SECONDS,
            safe_to_retry=True,
            operation="counterparty options lookup",
        )

    def get_counterparties(
        self,
        *,
        counterparty_property: str = "Sender",
        query: str = "",
        page: int = 1,
    ) -> NovaPoshtaResponse:
        method_properties: dict[str, Any] = {
            "CounterpartyProperty": counterparty_property or "Sender",
            "Page": str(max(1, page)),
        }
        normalized_query = query.strip()
        if normalized_query:
            method_properties["FindByString"] = normalized_query

        return self._request(
            model_name="CounterpartyGeneral",
            called_method="getCounterparties",
            method_properties=method_properties,
            timeout=LOOKUP_TIMEOUT_SECONDS,
            safe_to_retry=True,
            operation="counterparties lookup",
        )

    def get_counterparty_contact_persons(self, *, counterparty_ref: str) -> NovaPoshtaResponse:
        return self._request(
            model_name="CounterpartyGeneral",
            called_method="getCounterpartyContactPersons",
            method_properties={"Ref": counterparty_ref},
            timeout=LOOKUP_TIMEOUT_SECONDS,
            safe_to_retry=True,
            operation="counterparty contacts lookup",
        )

    def get_counterparty_addresses(
        self,
        *,
        counterparty_ref: str,
        counterparty_property: str = "Sender",
    ) -> NovaPoshtaResponse:
        method_properties = {
            "Ref": counterparty_ref,
            "CounterpartyProperty": counterparty_property or "Sender",
        }
        try:
            return self._request(
                model_name="CounterpartyGeneral",
                called_method="getCounterpartyAddresses",
                method_properties=method_properties,
                timeout=LOOKUP_TIMEOUT_SECONDS,
                safe_to_retry=True,
                operation="counterparty addresses lookup",
            )
        except NovaPoshtaIntegrationError:
            pass

        try:
            return self._request(
                model_name="AddressGeneral",
                called_method="getCounterpartyAddresses",
                method_properties=method_properties,
                timeout=LOOKUP_TIMEOUT_SECONDS,
                safe_to_retry=True,
                operation="counterparty addresses lookup",
            )
        except NovaPoshtaIntegrationError:
            return self._request(
                model_name="Address",
                called_method="getCounterpartyAddresses",
                method_properties=method_properties,
                timeout=LOOKUP_TIMEOUT_SECONDS,
                safe_to_retry=True,
                operation="counterparty addresses lookup",
            )

    def create_waybill(self, *, method_properties: dict[str, Any]) -> NovaPoshtaResponse:
        return self._request(
            model_name="InternetDocumentGeneral",
            called_method="save",
            method_properties=method_properties,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            safe_to_retry=False,
            operation="create waybill",
        )

    def update_waybill(self, *, method_properties: dict[str, Any]) -> NovaPoshtaResponse:
        return self._request(
            model_name="InternetDocumentGeneral",
            called_method="update",
            method_properties=method_properties,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            safe_to_retry=False,
            operation="update waybill",
        )

    def delete_waybill(self, *, np_ref: str) -> NovaPoshtaResponse:
        return self._request(
            model_name="InternetDocumentGeneral",
            called_method="delete",
            method_properties={"DocumentRefs": np_ref},
            timeout=DEFAULT_TIMEOUT_SECONDS,
            safe_to_retry=False,
            operation="delete waybill",
        )

    def get_tracking_status(self, *, document_number: str, phone: str) -> NovaPoshtaResponse:
        return self._request(
            model_name="TrackingDocumentGeneral",
            called_method="getStatusDocuments",
            method_properties={"Documents": [{"DocumentNumber": document_number, "Phone": phone}]},
            timeout=DEFAULT_TIMEOUT_SECONDS,
            safe_to_retry=True,
            operation="waybill tracking",
        )

    def download_print_form(self, *, identifier: str, fmt: str) -> tuple[bytes, str]:
        normalized_fmt = fmt if fmt in {"html", "pdf"} else "html"
        url = f"{NOVA_POSHTA_PRINT_BASE_URL}/printDocument/orders[]/{identifier}/type/{normalized_fmt}/apiKey/{self.api_token}"
        request = Request(url=url, method="GET")

        logger.info("Nova Poshta print request", extra={"identifier": identifier, "format": normalized_fmt})
        try:
            with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                body = response.read()
                content_type = str(response.headers.get("Content-Type") or "application/octet-stream")
                return body, content_type
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
            payload = _json_or_empty(raw)
            raise map_error_from_payload(
                payload=payload,
                default_message="Новая Почта вернула ошибку при формировании печатной формы.",
                status_code=exc.code,
            ) from exc
        except (URLError, socket.timeout) as exc:
            raise NovaPoshtaIntegrationError("Не удалось получить печатную форму ТТН от Новой Почты.") from exc

    def _request(
        self,
        *,
        model_name: str,
        called_method: str,
        method_properties: dict[str, Any],
        timeout: int,
        safe_to_retry: bool,
        operation: str,
    ) -> NovaPoshtaResponse:
        payload = {
            "apiKey": self.api_token,
            "modelName": model_name,
            "calledMethod": called_method,
            "methodProperties": method_properties,
        }
        request = Request(
            url=NOVA_POSHTA_API_URL,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload).encode("utf-8"),
        )

        attempts = 2 if safe_to_retry else 1
        for attempt in range(1, attempts + 1):
            try:
                logger.info(
                    "Nova Poshta request",
                    extra={
                        "operation": operation,
                        "model": model_name,
                        "method": called_method,
                        "attempt": attempt,
                    },
                )
                with urlopen(request, timeout=timeout) as response:
                    raw = response.read().decode("utf-8", errors="ignore")
                    body = _json_or_empty(raw)
                    if not isinstance(body, dict):
                        body = {}

                    context = extract_error_context(body)
                    is_success = bool(body.get("success"))
                    has_errors = bool(context.errors or context.error_codes)
                    if not is_success or has_errors:
                        raise map_error_from_payload(
                            payload=body,
                            default_message="Новая Почта вернула ошибку по запросу.",
                            status_code=response.status,
                        )

                    logger.info(
                        "Nova Poshta response",
                        extra={
                            "operation": operation,
                            "model": model_name,
                            "method": called_method,
                            "status": response.status,
                            "success": is_success,
                        },
                    )
                    return NovaPoshtaResponse(payload=body, context=context)
            except HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
                body = _json_or_empty(raw)
                logger.warning(
                    "Nova Poshta HTTP error",
                    extra={
                        "operation": operation,
                        "model": model_name,
                        "method": called_method,
                        "status_code": exc.code,
                        "attempt": attempt,
                    },
                )
                raise map_error_from_payload(
                    payload=body,
                    default_message="Новая Почта вернула HTTP ошибку.",
                    status_code=exc.code,
                ) from exc
            except NovaPoshtaIntegrationError:
                raise
            except (URLError, socket.timeout, TimeoutError) as exc:
                if attempt < attempts:
                    logger.warning(
                        "Nova Poshta temporary transport error",
                        extra={
                            "operation": operation,
                            "model": model_name,
                            "method": called_method,
                            "attempt": attempt,
                        },
                    )
                    continue
                raise NovaPoshtaIntegrationError("Не удалось выполнить запрос к Новой Почте.") from exc
            except json.JSONDecodeError as exc:
                raise NovaPoshtaIntegrationError("Новая Почта вернула некорректный JSON.") from exc

        raise NovaPoshtaIntegrationError("Не удалось выполнить запрос к Новой Почте.")


def _json_or_empty(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return data
    return {}
