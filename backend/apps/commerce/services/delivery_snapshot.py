from __future__ import annotations

from typing import Any

from apps.commerce.models import Order


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _looks_like_region_token(value: str) -> bool:
    normalized = _clean(value).lower()
    if not normalized:
        return False

    if "область" in normalized:
        return True

    return normalized.endswith(("обл", "обл.", "ская", "ська", "ский", "ський"))


def _split_delivery_address(value: str) -> tuple[str, str, str]:
    raw = _clean(value)
    if not raw:
        return "", "", ""

    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        return "", "", ""

    if len(parts) >= 3 and _looks_like_region_token(parts[0]):
        return parts[1], ", ".join(parts[2:]).strip(), parts[0]

    if len(parts) >= 3 and _looks_like_region_token(parts[1]):
        return parts[0], ", ".join(parts[2:]).strip(), parts[1]

    city_index = 0
    destination_start_index = 1
    region = ""
    if len(parts) > 1 and _looks_like_region_token(parts[0]):
        city_index = 1
        destination_start_index = 2
        region = parts[0]

    city = parts[city_index] if len(parts) > city_index else ""
    destination = ", ".join(parts[destination_start_index:]).strip()
    return city, destination, region


def _normalize_city_with_region(city: str, region: str) -> str:
    normalized_city = _clean(city)
    normalized_region = _clean(region)
    if not normalized_city and not normalized_region:
        return ""
    if not normalized_region:
        return normalized_city
    if not normalized_city:
        return normalized_region

    city_parts = [part.strip() for part in normalized_city.split(",") if part.strip()]
    lower_region = normalized_region.lower()
    if any(part.lower() == lower_region for part in city_parts[1:]):
        return normalized_city

    lower_city = normalized_city.lower()
    if lower_city.startswith("г. ") or lower_city.startswith("м. "):
        return f"{normalized_city}, {normalized_region}"
    return f"г. {normalized_city}, {normalized_region}"


def _is_postomat_token(value: str) -> bool:
    normalized = _clean(value).lower()
    return any(token in normalized for token in ("postomat", "поштомат", "постомат", "почтомат"))


def _normalize_method(delivery_method: str) -> str:
    normalized = _clean(delivery_method).lower()
    if normalized in (Order.DELIVERY_PICKUP, Order.DELIVERY_COURIER, Order.DELIVERY_NOVA_POSHTA):
        return normalized
    return Order.DELIVERY_PICKUP


def _normalize_delivery_type(raw_type: str, *, fallback_label: str = "") -> str:
    normalized = _clean(raw_type).lower()
    if normalized in ("warehouse", "postomat", "address"):
        return normalized
    return "postomat" if _is_postomat_token(fallback_label) else "warehouse"


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def build_delivery_snapshot_from_checkout(*, delivery_method: str, delivery_address: str, delivery_snapshot: Any) -> dict[str, Any]:
    normalized_method = _normalize_method(delivery_method)
    cleaned_address = _clean(delivery_address)

    snapshot_input = _safe_dict(delivery_snapshot)
    result: dict[str, Any] = {
        "method": normalized_method,
        "delivery_address": cleaned_address,
    }

    if normalized_method == Order.DELIVERY_PICKUP:
        return result

    city_from_address, destination_from_address, region_from_address = _split_delivery_address(cleaned_address)

    if normalized_method == Order.DELIVERY_COURIER:
        courier_input = _safe_dict(snapshot_input.get("courier"))
        city_label = _clean(courier_input.get("city_label")) or _clean(snapshot_input.get("city_label")) or city_from_address
        destination_label = _clean(courier_input.get("destination_label")) or _clean(snapshot_input.get("destination_label")) or destination_from_address
        street_ref = _clean(courier_input.get("street_ref")) or _clean(snapshot_input.get("street_ref"))
        street_label = _clean(courier_input.get("street_label")) or _clean(snapshot_input.get("street_label"))
        house = _clean(courier_input.get("house")) or _clean(snapshot_input.get("house"))
        apartment = _clean(courier_input.get("apartment")) or _clean(snapshot_input.get("apartment"))

        result["courier"] = {
            "city_label": city_label,
            "region_label": _clean(courier_input.get("region_label")) or _clean(snapshot_input.get("region_label")) or region_from_address,
            "destination_label": destination_label,
            "street_ref": street_ref,
            "street_label": street_label,
            "house": house,
            "apartment": apartment,
        }
        return result

    # Nova Poshta
    np_input = _safe_dict(snapshot_input.get("nova_poshta"))
    city_label = _clean(np_input.get("city_label")) or _clean(snapshot_input.get("city_label")) or city_from_address
    region_label = _clean(np_input.get("region_label")) or _clean(snapshot_input.get("region_label")) or region_from_address
    destination_label = _clean(np_input.get("destination_label")) or _clean(snapshot_input.get("destination_label")) or destination_from_address

    raw_delivery_type = _clean(np_input.get("delivery_type")) or _clean(snapshot_input.get("delivery_type"))
    delivery_type = _normalize_delivery_type(raw_delivery_type, fallback_label=destination_label)

    warehouse_input = _safe_dict(np_input.get("warehouse"))
    street_input = _safe_dict(np_input.get("street"))

    destination_ref = _clean(np_input.get("destination_ref")) or _clean(snapshot_input.get("destination_ref"))
    city_ref = _clean(np_input.get("city_ref")) or _clean(snapshot_input.get("city_ref"))
    settlement_ref = _clean(np_input.get("settlement_ref")) or _clean(snapshot_input.get("settlement_ref"))

    warehouse_ref = _clean(warehouse_input.get("ref")) or _clean(np_input.get("warehouse_ref")) or destination_ref
    warehouse_number = _clean(warehouse_input.get("number")) or _clean(np_input.get("warehouse_number"))
    warehouse_type = _clean(warehouse_input.get("type")) or _clean(np_input.get("warehouse_type"))
    warehouse_category = _clean(warehouse_input.get("category")) or _clean(np_input.get("warehouse_category"))
    warehouse_label = _clean(warehouse_input.get("label")) or _clean(np_input.get("warehouse_label")) or destination_label

    street_ref = _clean(street_input.get("street_ref")) or _clean(np_input.get("street_ref")) or _clean(snapshot_input.get("street_ref"))
    street_label = _clean(street_input.get("street_label")) or _clean(np_input.get("street_label")) or _clean(snapshot_input.get("street_label"))
    house = _clean(street_input.get("house")) or _clean(np_input.get("house")) or _clean(snapshot_input.get("house"))
    apartment = _clean(street_input.get("apartment")) or _clean(np_input.get("apartment")) or _clean(snapshot_input.get("apartment"))

    result["nova_poshta"] = {
        "delivery_type": delivery_type,
        "city_ref": city_ref,
        "city_label": city_label,
        "settlement_ref": settlement_ref,
        "area_label": _clean(np_input.get("area_label")) or _clean(snapshot_input.get("area_label")),
        "region_label": region_label,
        "destination_ref": destination_ref or warehouse_ref or street_ref,
        "destination_label": destination_label or warehouse_label or street_label,
        "warehouse": {
            "ref": warehouse_ref,
            "number": warehouse_number,
            "type": warehouse_type,
            "category": warehouse_category,
            "label": warehouse_label,
        },
        "street": {
            "street_ref": street_ref,
            "street_label": street_label,
            "house": house,
            "apartment": apartment,
        },
    }
    return result


def resolve_delivery_display(*, delivery_method: str, delivery_address: str, delivery_snapshot: Any) -> tuple[str, str]:
    normalized_method = _normalize_method(delivery_method)
    snapshot = _safe_dict(delivery_snapshot)

    if normalized_method == Order.DELIVERY_NOVA_POSHTA:
        np_data = _safe_dict(snapshot.get("nova_poshta"))
        np_city = _clean(np_data.get("city_label"))
        np_region = _clean(np_data.get("region_label"))
        city_label = _normalize_city_with_region(np_city, np_region) or np_city
        destination_label = _clean(np_data.get("destination_label"))
        if city_label or destination_label:
            return city_label, destination_label

    if normalized_method == Order.DELIVERY_COURIER:
        courier_data = _safe_dict(snapshot.get("courier"))
        city_label = _clean(courier_data.get("city_label"))
        destination_label = _clean(courier_data.get("destination_label"))
        if city_label or destination_label:
            return city_label, destination_label

    city_from_address, destination_from_address, region_from_address = _split_delivery_address(delivery_address)
    if normalized_method == Order.DELIVERY_NOVA_POSHTA:
        return (
            _normalize_city_with_region(city_from_address, region_from_address) or city_from_address,
            destination_from_address,
        )
    return city_from_address, destination_from_address


def resolve_waybill_seed(*, delivery_method: str, delivery_address: str, delivery_snapshot: Any) -> dict[str, str]:
    snapshot = _safe_dict(delivery_snapshot)
    method = _normalize_method(delivery_method)
    city_from_display, destination_from_display = resolve_delivery_display(
        delivery_method=method,
        delivery_address=delivery_address,
        delivery_snapshot=snapshot,
    )

    seed = {
        "delivery_type": "warehouse",
        "recipient_city_ref": "",
        "recipient_city_label": city_from_display,
        "recipient_address_ref": "",
        "recipient_address_label": "",
        "recipient_street_ref": "",
        "recipient_street_label": "",
        "recipient_house": "",
        "recipient_apartment": "",
    }

    if method == Order.DELIVERY_COURIER:
        courier_data = _safe_dict(snapshot.get("courier"))
        seed.update(
            {
                "delivery_type": "address",
                "recipient_address_label": _clean(courier_data.get("destination_label")) or destination_from_display,
                "recipient_street_ref": _clean(courier_data.get("street_ref")),
                "recipient_street_label": _clean(courier_data.get("street_label")),
                "recipient_house": _clean(courier_data.get("house")),
                "recipient_apartment": _clean(courier_data.get("apartment")),
            }
        )
        return seed

    if method != Order.DELIVERY_NOVA_POSHTA:
        return seed

    np_data = _safe_dict(snapshot.get("nova_poshta"))
    warehouse_data = _safe_dict(np_data.get("warehouse"))
    street_data = _safe_dict(np_data.get("street"))

    delivery_type = _normalize_delivery_type(
        _clean(np_data.get("delivery_type")),
        fallback_label=_clean(np_data.get("destination_label")) or destination_from_display,
    )
    seed["delivery_type"] = delivery_type
    seed["recipient_city_ref"] = _clean(np_data.get("city_ref"))
    seed["recipient_city_label"] = _clean(np_data.get("city_label")) or city_from_display
    seed["recipient_address_ref"] = (
        _clean(np_data.get("destination_ref"))
        or _clean(warehouse_data.get("ref"))
        or seed["recipient_address_ref"]
    )
    seed["recipient_address_label"] = (
        _clean(np_data.get("destination_label"))
        or _clean(warehouse_data.get("label"))
        or destination_from_display
    )
    seed["recipient_street_ref"] = _clean(street_data.get("street_ref")) or _clean(np_data.get("street_ref"))
    seed["recipient_street_label"] = _clean(street_data.get("street_label")) or _clean(np_data.get("street_label"))
    seed["recipient_house"] = _clean(street_data.get("house")) or _clean(np_data.get("house"))
    seed["recipient_apartment"] = _clean(street_data.get("apartment")) or _clean(np_data.get("apartment"))

    if delivery_type == "address":
        seed["recipient_address_ref"] = ""
        if not seed["recipient_address_label"]:
            address_parts = [seed["recipient_street_label"], seed["recipient_house"], seed["recipient_apartment"]]
            seed["recipient_address_label"] = ", ".join(part for part in address_parts if part)

    return seed
