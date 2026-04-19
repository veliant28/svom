from __future__ import annotations

from datetime import datetime
from typing import Any

from .errors import NovaPoshtaErrorContext


def _to_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def extract_error_context(payload: dict[str, Any] | None) -> NovaPoshtaErrorContext:
    payload = payload or {}
    return NovaPoshtaErrorContext(
        errors=_to_string_list(payload.get("errors")),
        warnings=_to_string_list(payload.get("warnings")),
        info=_to_string_list(payload.get("info")),
        error_codes=_to_string_list(payload.get("errorCodes")),
        warning_codes=_to_string_list(payload.get("warningCodes")),
        info_codes=_to_string_list(payload.get("infoCodes")),
        raw_response=payload if isinstance(payload, dict) else {},
    )


def first_data_item(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    data = payload.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return first
    if isinstance(data, dict):
        return data
    return {}


def normalize_settlements(payload: dict[str, Any], *, locale: str = "uk") -> list[dict[str, Any]]:
    item = first_data_item(payload)
    addresses = item.get("Addresses")
    if not isinstance(addresses, list):
        return []
    locale_is_ru = _is_ru_locale(locale)

    localized = []
    for candidate in addresses:
        if not isinstance(candidate, dict):
            continue
        main_description_uk = str(candidate.get("MainDescription") or "").strip()
        main_description_ru = str(candidate.get("MainDescriptionRu") or candidate.get("MainDescriptionRU") or "").strip()
        area_uk = str(candidate.get("Area") or "").strip()
        area_ru = str(candidate.get("AreaRu") or candidate.get("AreaDescriptionRu") or "").strip()
        region_uk = str(candidate.get("Region") or "").strip()
        region_ru = str(candidate.get("RegionRu") or candidate.get("RegionsDescriptionRu") or "").strip()
        settlement_type_uk = str(candidate.get("SettlementTypeCode") or "").strip()
        settlement_type_ru = str(candidate.get("SettlementTypeCodeRu") or "").strip()
        present_uk = str(candidate.get("Present") or "").strip()
        present_ru = str(candidate.get("PresentRu") or candidate.get("PresentRU") or "").strip()

        has_ru_context = bool(present_ru or main_description_ru)
        if locale_is_ru and has_ru_context:
            main_description = main_description_ru or ""
            area = area_ru or ""
            region = region_ru or ""
            settlement_type = settlement_type_ru or ""
            composed_label = _compose_settlement_label(
                settlement_type=settlement_type,
                main_description=main_description,
                area=area,
                region=region,
            )
            label = present_ru or composed_label or present_uk
        else:
            # Keep the whole string in one locale to avoid mixed-language labels.
            main_description = main_description_uk or main_description_ru
            area = area_uk or area_ru
            region = region_uk or region_ru
            settlement_type = settlement_type_uk or settlement_type_ru
            composed_label = _compose_settlement_label(
                settlement_type=settlement_type,
                main_description=main_description,
                area=area,
                region=region,
            )
            label = present_uk or composed_label or present_ru

        localized.append(
            {
                "ref": str(candidate.get("Ref") or ""),
                "delivery_city_ref": str(candidate.get("DeliveryCity") or ""),
                "settlement_ref": str(candidate.get("SettlementRef") or candidate.get("Ref") or ""),
                "label": label,
                "main_description": main_description,
                "area": area,
                "region": region,
                "address_delivery_allowed": bool(candidate.get("AddressDeliveryAllowed")),
                "streets_available": bool(candidate.get("StreetsAvailability")),
                "warehouses_count": str(candidate.get("Warehouses") or ""),
                "locale": locale,
            }
        )
    return localized


def normalize_cities(payload: dict[str, Any], *, locale: str = "uk") -> list[dict[str, str]]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    locale_is_ru = _is_ru_locale(locale)

    normalized: list[dict[str, str]] = []
    for candidate in data:
        if not isinstance(candidate, dict):
            continue
        ref = str(candidate.get("Ref") or "").strip()
        if not ref:
            continue
        description_uk = str(candidate.get("Description") or "").strip()
        description_ru = str(candidate.get("DescriptionRu") or "").strip()
        settlement_type_uk = str(candidate.get("SettlementTypeDescription") or "").strip()
        settlement_type_ru = str(candidate.get("SettlementTypeDescriptionRu") or "").strip()
        name = description_ru if locale_is_ru and description_ru else description_uk or description_ru
        settlement_type = settlement_type_ru if locale_is_ru and settlement_type_ru else settlement_type_uk or settlement_type_ru
        normalized.append(
            {
                "ref": ref,
                "name": name,
                "settlement_type": settlement_type,
                "name_uk": description_uk or description_ru,
                "name_ru": description_ru or description_uk,
                "settlement_type_uk": settlement_type_uk or settlement_type_ru,
                "settlement_type_ru": settlement_type_ru or settlement_type_uk,
            }
        )
    return normalized


def normalize_streets(payload: dict[str, Any], *, locale: str = "uk") -> list[dict[str, Any]]:
    item = first_data_item(payload)
    addresses = item.get("Addresses")
    if not isinstance(addresses, list):
        return []
    locale_is_ru = _is_ru_locale(locale)

    normalized = []
    for candidate in addresses:
        if not isinstance(candidate, dict):
            continue
        street_name_uk = str(candidate.get("SettlementStreetDescription") or "").strip()
        street_name_ru = str(candidate.get("SettlementStreetDescriptionRu") or "").strip()
        street_type_uk = str(
            candidate.get("StreetsTypeDescription")
            or candidate.get("StreetTypeDescription")
            or candidate.get("StreetsType")
            or ""
        ).strip()
        street_type_ru = str(
            candidate.get("StreetsTypeDescriptionRu")
            or candidate.get("StreetTypeDescriptionRu")
            or candidate.get("StreetsTypeRu")
            or ""
        ).strip()
        present_uk = str(candidate.get("Present") or "").strip()
        present_ru = str(candidate.get("PresentRu") or "").strip()
        if locale_is_ru:
            present_label_ru = present_ru or _map_uk_street_present_to_ru(present_uk)
            street_name = (
                street_name_ru
                or _extract_street_name_from_present(present_label_ru)
                or street_name_uk
                or _extract_street_name_from_present(present_uk)
            )
            street_type = _normalize_ru_street_type(
                street_type_ru
                or _map_uk_street_type_to_ru(street_type_uk)
                or _extract_street_type_from_present(present_label_ru)
                or _map_uk_street_type_to_ru(_extract_street_type_from_present(present_uk))
            )
            composed_label = _compose_street_label(street_type=street_type, street_name=street_name)
            label = composed_label or present_label_ru or street_name
        else:
            # Keep one-locale fallback to avoid mixed-language labels.
            street_name = street_name_uk or street_name_ru
            street_type = street_type_uk or street_type_ru
            composed_label = _compose_street_label(street_type=street_type, street_name=street_name)
            label = present_uk or composed_label or present_ru
        normalized.append(
            {
                "settlement_ref": str(candidate.get("SettlementRef") or ""),
                "street_ref": str(candidate.get("SettlementStreetRef") or ""),
                "label": label,
                "street_name": street_name_uk or street_name,
                "street_name_ru": street_name_ru or street_name,
                "street_type": street_type,
            }
        )
    return normalized


def normalize_warehouses(payload: dict[str, Any], *, locale: str = "uk") -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    locale_is_ru = _is_ru_locale(locale)

    normalized = []
    for candidate in data:
        if not isinstance(candidate, dict):
            continue

        description = str(candidate.get("Description") or "")
        description_ru = str(candidate.get("DescriptionRu") or "")
        short_address = str(candidate.get("ShortAddress") or "")
        short_address_ru = str(candidate.get("ShortAddressRu") or "")

        label = description_ru if locale_is_ru and description_ru else description or description_ru
        short_label = short_address_ru if locale_is_ru and short_address_ru else short_address or short_address_ru
        final_label = short_label or label

        normalized.append(
            {
                "ref": str(candidate.get("Ref") or ""),
                "number": str(candidate.get("Number") or ""),
                "city_ref": str(candidate.get("CityRef") or ""),
                "settlement_ref": str(candidate.get("SettlementRef") or ""),
                "type": str(candidate.get("TypeOfWarehouse") or ""),
                "category": str(candidate.get("CategoryOfWarehouse") or ""),
                "label": final_label,
                "description": label,
                "full_description": label,
                "post_finance": str(candidate.get("PostFinance") or "") == "1",
            }
        )
    return normalized


def normalize_pack_list(payload: dict[str, Any], *, locale: str = "uk") -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []

    normalized: list[dict[str, Any]] = []
    locale_is_ru = locale.lower().startswith("ru")
    for candidate in data:
        if not isinstance(candidate, dict):
            continue
        ref = str(candidate.get("Ref") or candidate.get("ref") or candidate.get("PackRef") or "").strip()
        if not ref:
            continue
        description = str(candidate.get("Description") or candidate.get("TypeOfPacking") or "").strip()
        description_ru = str(candidate.get("DescriptionRu") or candidate.get("TypeOfPackingRu") or "").strip()
        label = description_ru if locale_is_ru and description_ru else description or description_ru or ref
        normalized.append(
            {
                "ref": ref,
                "label": label,
                "description": description or label,
                "description_ru": description_ru or description or label,
                "length_mm": str(candidate.get("Length") or candidate.get("length") or "").strip(),
                "width_mm": str(candidate.get("Width") or candidate.get("width") or "").strip(),
                "height_mm": str(candidate.get("Height") or candidate.get("height") or "").strip(),
                "cost": str(
                    candidate.get("Cost")
                    or candidate.get("CostPack")
                    or candidate.get("CostOfServices")
                    or ""
                ).strip(),
            }
        )
    return normalized


def normalize_counterparty_contacts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []

    normalized = []
    for candidate in data:
        if not isinstance(candidate, dict):
            continue
        phone = str(candidate.get("Phones") or candidate.get("Phone") or "").strip()
        normalized.append(
            {
                "ref": str(candidate.get("Ref") or ""),
                "name": str(candidate.get("Description") or candidate.get("FullName") or "").strip(),
                "phone": phone,
            }
        )
    return normalized


def normalize_counterparty_addresses(payload: dict[str, Any], *, locale: str = "uk") -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    locale_is_ru = _is_ru_locale(locale)

    normalized = []
    for candidate in data:
        if not isinstance(candidate, dict):
            continue
        description = str(candidate.get("Description") or "").strip()
        description_ru = str(candidate.get("DescriptionRu") or "").strip()
        label = description_ru if locale_is_ru and description_ru else description or description_ru
        city_label = str(
            candidate.get("CityDescription")
            or candidate.get("CityDescriptionRu")
            or candidate.get("SettlementDescription")
            or candidate.get("City")
            or ""
        ).strip()
        normalized.append(
            {
                "ref": str(candidate.get("Ref") or ""),
                "city_ref": str(candidate.get("CityRef") or candidate.get("SettlementRef") or candidate.get("City") or "").strip(),
                "city_label": city_label,
                "label": label,
            }
        )
    return normalized


def _compose_settlement_label(*, settlement_type: str, main_description: str, area: str, region: str) -> str:
    normalized_type = (settlement_type or "").strip()
    normalized_main = (main_description or "").strip()
    normalized_area = (area or "").strip()
    normalized_region = (region or "").strip()

    city_part = ""
    if normalized_type and normalized_main:
        if normalized_main.lower().startswith(normalized_type.lower()):
            city_part = normalized_main
        else:
            city_part = f"{normalized_type} {normalized_main}".strip()
    else:
        city_part = normalized_main or normalized_type

    base = ", ".join(part for part in [city_part, normalized_area] if part)
    if normalized_region:
        return f"{base} ({normalized_region})" if base else normalized_region
    return base


def _compose_street_label(*, street_type: str, street_name: str) -> str:
    normalized_type = (street_type or "").strip()
    normalized_name = (street_name or "").strip()
    if not normalized_type:
        return normalized_name
    if not normalized_name:
        return normalized_type
    if normalized_name.lower().startswith(normalized_type.lower()):
        return normalized_name
    return f"{normalized_type} {normalized_name}".strip()


def _is_ru_locale(locale: str) -> bool:
    return (locale or "").strip().lower().startswith("ru")


def _map_uk_street_type_to_ru(value: str) -> str:
    return _normalize_ru_street_type(value)


def _map_uk_street_present_to_ru(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    street_type = _extract_street_type_from_present(normalized)
    if not street_type:
        return normalized
    mapped_type = _normalize_ru_street_type(street_type)
    if not mapped_type:
        return normalized
    tail = normalized[len(street_type):].lstrip()
    return f"{mapped_type} {tail}".strip()


def _extract_street_type_from_present(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    first_token = normalized.split(" ", 1)[0].strip()
    return first_token


def _extract_street_name_from_present(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    parts = normalized.split(" ", 1)
    if len(parts) < 2:
        return normalized
    return parts[1].strip()


def _normalize_ru_street_type(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    key = normalized.lower().strip(".")
    table = {
        "вул": "ул.",
        "вулиця": "ул.",
        "улица": "ул.",
        "ул": "ул.",
        "просп": "просп.",
        "проспект": "просп.",
        "пр-кт": "просп.",
        "пр": "просп.",
        "пров": "пер.",
        "провулок": "пер.",
        "пер": "пер.",
        "переулок": "пер.",
        "бульвар": "бул.",
        "бульв": "бул.",
        "бул": "бул.",
        "б-р": "бул.",
        "площа": "пл.",
        "площадь": "пл.",
        "пл": "пл.",
        "набережна": "наб.",
        "набережная": "наб.",
        "наб": "наб.",
        "проїзд": "пр-д",
        "проезд": "пр-д",
        "пр-д": "пр-д",
        "шосе": "шоссе",
        "шоссе": "шоссе",
        "тупик": "туп.",
        "туп": "туп.",
    }
    mapped = table.get(key)
    return mapped or normalized


def normalize_time_intervals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []

    normalized: list[dict[str, Any]] = []
    for candidate in data:
        if not isinstance(candidate, dict):
            continue
        number = str(candidate.get("Number") or "").strip()
        if not number:
            continue
        start = str(candidate.get("Start") or "").strip()
        end = str(candidate.get("End") or "").strip()
        if start and end:
            label = f"{start} - {end}"
        elif start:
            label = start
        elif end:
            label = end
        else:
            label = number
        normalized.append(
            {
                "number": number,
                "start": start,
                "end": end,
                "label": label,
            }
        )
    return normalized


def normalize_document_delivery_date(payload: dict[str, Any]) -> dict[str, str]:
    item = first_data_item(payload)
    delivery_date = item.get("DeliveryDate")
    if isinstance(delivery_date, dict):
        raw_datetime = str(delivery_date.get("date") or "").strip()
    else:
        raw_datetime = str(delivery_date or "").strip()
    return {
        "date": _format_dd_mm_yyyy(raw_datetime),
        "raw_datetime": raw_datetime,
    }


def _format_dd_mm_yyyy(raw_value: str) -> str:
    normalized = (raw_value or "").strip()
    if not normalized:
        return ""
    normalized = normalized.replace("T", " ").replace("Z", "").strip()

    for date_format in ("%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(normalized, date_format).strftime("%d.%m.%Y")
        except ValueError:
            continue

    if len(normalized) >= 10:
        candidate = normalized[:10]
        for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(candidate, date_format).strftime("%d.%m.%Y")
            except ValueError:
                continue
    return ""


def normalize_counterparties(payload: dict[str, Any], *, locale: str = "uk") -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []

    normalized = []
    for candidate in data:
        if not isinstance(candidate, dict):
            continue

        first_name = str(candidate.get("FirstName") or "").strip()
        last_name = str(candidate.get("LastName") or "").strip()
        middle_name = str(candidate.get("MiddleName") or "").strip()
        full_name = " ".join(part for part in [last_name, first_name, middle_name] if part).strip()
        description = str(candidate.get("Description") or "").strip()
        label = description or full_name
        city_ref = str(candidate.get("City") or "").strip()
        city_label = str(
            candidate.get("CityDescription")
            or candidate.get("CityDescriptionRu")
            or candidate.get("AreaDescription")
            or ""
        ).strip()
        if city_ref == "00000000-0000-0000-0000-000000000000":
            city_ref = ""

        normalized.append(
            {
                "ref": str(candidate.get("Ref") or ""),
                "counterparty_ref": str(candidate.get("Counterparty") or ""),
                "city_ref": city_ref,
                "city_label": city_label,
                "label": label,
                "full_name": full_name,
                "first_name": first_name,
                "last_name": last_name,
                "middle_name": middle_name,
                "phone": str(candidate.get("Phone") or candidate.get("Phones") or "").strip(),
                "address": str(candidate.get("Address") or candidate.get("PresentAddress") or "").strip(),
                "ownership_form_description": str(candidate.get("OwnershipFormDescription") or ""),
                "edrpou": str(candidate.get("EDRPOU") or ""),
                "counterparty_type": str(candidate.get("CounterpartyType") or ""),
                "locale": locale,
            }
        )
    return normalized
