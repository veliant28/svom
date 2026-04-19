from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from django.core.cache import cache

from .client import NovaPoshtaApiClient
from .errors import NovaPoshtaIntegrationError
from .normalizers import (
    normalize_cities,
    normalize_pack_list,
    normalize_counterparties,
    normalize_counterparty_addresses,
    normalize_counterparty_contacts,
    normalize_document_delivery_date,
    normalize_settlements,
    normalize_streets,
    normalize_time_intervals,
    normalize_warehouses,
)

_LOOKUP_CACHE_TTL_SECONDS = 60 * 5
_LOOKUP_CACHE_VERSION = "v4"


class NovaPoshtaLookupService:
    def __init__(self, *, api_token: str):
        self.client = NovaPoshtaApiClient(api_token=api_token)

    def search_settlements(self, *, query: str, locale: str = "uk") -> list[dict[str, Any]]:
        normalized_query = query.strip()
        if len(normalized_query) < 2:
            return []
        resolved_locale = _normalize_locale(locale)

        cache_key = _cache_key("settlements", normalized_query, resolved_locale)
        cached = cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        response = self.client.search_settlements(query=normalized_query)
        data = normalize_settlements(response.payload, locale=resolved_locale)
        if resolved_locale == "ru":
            try:
                cities_response = self.client.get_cities(query=normalized_query)
                cities = normalize_cities(cities_response.payload, locale="ru")
                cities_by_ref = {row["ref"]: row for row in cities if row.get("ref")}
                data = _apply_ru_city_overrides(rows=data, cities_by_ref=cities_by_ref)
            except NovaPoshtaIntegrationError:
                pass
        cache.set(cache_key, data, _LOOKUP_CACHE_TTL_SECONDS)
        return data

    def search_streets(self, *, settlement_ref: str, query: str, locale: str = "uk") -> list[dict[str, Any]]:
        normalized_query = query.strip()
        if not settlement_ref.strip() or len(normalized_query) < 2:
            return []
        resolved_locale = _normalize_locale(locale)

        cache_key = _cache_key("streets", settlement_ref, normalized_query, resolved_locale)
        cached = cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        response = self.client.search_streets(settlement_ref=settlement_ref.strip(), query=normalized_query)
        data = normalize_streets(response.payload, locale=resolved_locale)
        cache.set(cache_key, data, _LOOKUP_CACHE_TTL_SECONDS)
        return data

    def get_warehouses(
        self,
        *,
        city_ref: str,
        query: str = "",
        locale: str = "uk",
        warehouse_type_ref: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_city_ref = city_ref.strip()
        normalized_query = query.strip()
        if not normalized_city_ref and len(normalized_query) < 2:
            return []
        resolved_locale = _normalize_locale(locale)

        cache_key = _cache_key("warehouses", normalized_city_ref, normalized_query, resolved_locale, warehouse_type_ref or "")
        cached = cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        response = self.client.get_warehouses(
            city_ref=normalized_city_ref,
            query=normalized_query,
            warehouse_type_ref=warehouse_type_ref,
            language="RU" if resolved_locale == "ru" else "UA",
        )
        data = normalize_warehouses(response.payload, locale=resolved_locale)
        cache.set(cache_key, data, _LOOKUP_CACHE_TTL_SECONDS)
        return data

    def get_pack_list_special(
        self,
        *,
        length_mm: int | None = None,
        width_mm: int | None = None,
        height_mm: int | None = None,
        locale: str = "uk",
    ) -> list[dict[str, Any]]:
        normalized_length_mm = int(length_mm or 0)
        normalized_width_mm = int(width_mm or 0)
        normalized_height_mm = int(height_mm or 0)
        has_valid_dimensions = (
            normalized_length_mm > 0
            and normalized_width_mm > 0
            and normalized_height_mm > 0
        )

        cache_key = _cache_key(
            "pack-list-special",
            str(normalized_length_mm),
            str(normalized_width_mm),
            str(normalized_height_mm),
            locale,
        )
        cached = cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        data: list[dict[str, Any]] = []
        if has_valid_dimensions:
            response = self.client.get_pack_list_special(
                length_mm=normalized_length_mm,
                width_mm=normalized_width_mm,
                height_mm=normalized_height_mm,
                pack_for_sale="1",
            )
            data = normalize_pack_list(response.payload, locale=locale)
        if not data:
            response = self.client.get_pack_list(pack_for_sale="1")
            data = normalize_pack_list(response.payload, locale=locale)
        cache.set(cache_key, data, _LOOKUP_CACHE_TTL_SECONDS)
        return data

    def get_time_intervals(
        self,
        *,
        recipient_city_ref: str,
        date_time: str = "",
    ) -> list[dict[str, Any]]:
        normalized_city_ref = recipient_city_ref.strip()
        if not normalized_city_ref:
            return []

        normalized_date_time = _normalize_date_for_np(date_time)
        cache_key = _cache_key("time-intervals", normalized_city_ref, normalized_date_time)
        cached = cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        response = self.client.get_time_intervals(
            recipient_city_ref=normalized_city_ref,
            date_time=normalized_date_time,
        )
        data = normalize_time_intervals(response.payload)
        cache.set(cache_key, data, _LOOKUP_CACHE_TTL_SECONDS)
        return data

    def get_document_delivery_date(
        self,
        *,
        city_sender_ref: str,
        recipient_city_ref: str,
        delivery_type: str,
        date_time: str = "",
    ) -> dict[str, str]:
        normalized_city_sender_ref = city_sender_ref.strip()
        normalized_city_recipient_ref = recipient_city_ref.strip()
        if not normalized_city_sender_ref or not normalized_city_recipient_ref:
            return {"date": "", "raw_datetime": ""}

        normalized_date_time = _normalize_document_datetime_for_np(date_time)
        service_type = _resolve_lookup_service_type(delivery_type)
        cache_key = _cache_key(
            "delivery-date",
            normalized_city_sender_ref,
            normalized_city_recipient_ref,
            service_type,
            normalized_date_time,
        )
        cached = cache.get(cache_key)
        if isinstance(cached, dict):
            return {
                "date": str(cached.get("date") or "").strip(),
                "raw_datetime": str(cached.get("raw_datetime") or "").strip(),
            }

        response = self.client.get_document_delivery_date(
            date_time=normalized_date_time,
            service_type=service_type,
            city_sender=normalized_city_sender_ref,
            city_recipient=normalized_city_recipient_ref,
        )
        result = normalize_document_delivery_date(response.payload)
        cache.set(cache_key, result, _LOOKUP_CACHE_TTL_SECONDS)
        return result

    def search_counterparties(
        self,
        *,
        query: str,
        counterparty_property: str = "Sender",
        locale: str = "uk",
    ) -> list[dict[str, Any]]:
        normalized_query = query.strip()
        if len(normalized_query) < 2:
            return []

        cache_key = _cache_key("counterparties", counterparty_property, normalized_query, locale)
        cached = cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        response = self.client.get_counterparties(
            counterparty_property=counterparty_property or "Sender",
            query=normalized_query,
        )
        data = normalize_counterparties(response.payload, locale=locale)
        cache.set(cache_key, data, _LOOKUP_CACHE_TTL_SECONDS)
        return data

    def get_counterparty_details(
        self,
        *,
        counterparty_ref: str,
        counterparty_property: str = "Sender",
        locale: str = "uk",
    ) -> dict[str, str]:
        normalized_ref = counterparty_ref.strip()
        if not normalized_ref:
            return {
                "contact_ref": "",
                "contact_name": "",
                "phone": "",
                "city_ref": "",
                "city_label": "",
                "address_ref": "",
                "address_label": "",
            }

        cache_key = _cache_key("counterparty-details", normalized_ref, counterparty_property, locale)
        cached = cache.get(cache_key)
        if isinstance(cached, dict):
            return cached

        contacts: list[dict[str, Any]] = []
        addresses: list[dict[str, Any]] = []
        try:
            contacts_response = self.client.get_counterparty_contact_persons(counterparty_ref=normalized_ref)
            contacts = normalize_counterparty_contacts(contacts_response.payload)
        except NovaPoshtaIntegrationError:
            contacts = []

        try:
            addresses_response = self.client.get_counterparty_addresses(
                counterparty_ref=normalized_ref,
                counterparty_property=counterparty_property or "Sender",
            )
            addresses = normalize_counterparty_addresses(addresses_response.payload, locale=locale)
        except NovaPoshtaIntegrationError:
            addresses = []

        first_contact = contacts[0] if contacts else {}
        first_address = addresses[0] if addresses else {}

        result = {
            "contact_ref": str(first_contact.get("ref") or ""),
            "contact_name": str(first_contact.get("name") or ""),
            "phone": str(first_contact.get("phone") or ""),
            "city_ref": str(first_address.get("city_ref") or ""),
            "city_label": str(first_address.get("city_label") or ""),
            "address_ref": str(first_address.get("ref") or ""),
            "address_label": str(first_address.get("label") or ""),
        }
        cache.set(cache_key, result, _LOOKUP_CACHE_TTL_SECONDS)
        return result


def _cache_key(prefix: str, *parts: str) -> str:
    raw = "::".join(part.strip().lower() for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"nova-poshta:{_LOOKUP_CACHE_VERSION}:{prefix}:{digest}"


def _normalize_locale(locale: str) -> str:
    normalized = (locale or "").strip().lower()
    return "ru" if normalized.startswith("ru") else "uk"


def _apply_ru_city_overrides(
    *,
    rows: list[dict[str, Any]],
    cities_by_ref: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    if not rows or not cities_by_ref:
        return rows

    updated: list[dict[str, Any]] = []
    for row in rows:
        city_ref = str(row.get("delivery_city_ref") or row.get("ref") or "").strip()
        city = cities_by_ref.get(city_ref)
        if not city:
            updated.append(row)
            continue

        city_name = str(city.get("name") or "").strip()
        settlement_type = _normalize_ru_settlement_type(str(city.get("settlement_type") or ""))
        if not city_name:
            updated.append(row)
            continue

        area = _map_uk_area_to_ru(str(row.get("area") or ""))
        label = _compose_city_label(
            settlement_type=settlement_type,
            city_name=city_name,
            area=area,
        )
        next_row = dict(row)
        next_row["main_description"] = city_name
        if settlement_type:
            next_row["settlement_type"] = settlement_type
        if area:
            next_row["area"] = area
        next_row["label"] = label
        updated.append(next_row)
    return updated


def _compose_city_label(*, settlement_type: str, city_name: str, area: str) -> str:
    normalized_type = (settlement_type or "").strip()
    normalized_city = (city_name or "").strip()
    normalized_area = (area or "").strip()

    city_part = normalized_city
    if normalized_type:
        city_part = (
            normalized_city
            if normalized_city.lower().startswith(normalized_type.lower())
            else f"{normalized_type} {normalized_city}".strip()
        )
    return ", ".join(part for part in [city_part, normalized_area] if part)


def _map_uk_area_to_ru(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    table = {
        "Вінницька": "Винницкая",
        "Волинська": "Волынская",
        "Дніпропетровська": "Днепропетровская",
        "Донецька": "Донецкая",
        "Житомирська": "Житомирская",
        "Закарпатська": "Закарпатская",
        "Запорізька": "Запорожская",
        "Івано-Франківська": "Ивано-Франковская",
        "Київська": "Киевская",
        "Кіровоградська": "Кировоградская",
        "Луганська": "Луганская",
        "Львівська": "Львовская",
        "Миколаївська": "Николаевская",
        "Одеська": "Одесская",
        "Полтавська": "Полтавская",
        "Рівненська": "Ровенская",
        "Сумська": "Сумская",
        "Тернопільська": "Тернопольская",
        "Харківська": "Харьковская",
        "Херсонська": "Херсонская",
        "Хмельницька": "Хмельницкая",
        "Черкаська": "Черкасская",
        "Чернівецька": "Черновицкая",
        "Чернігівська": "Черниговская",
    }
    mapped = table.get(normalized)
    return mapped or normalized


def _normalize_ru_settlement_type(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    key = normalized.lower().strip(".")
    table = {
        "город": "г.",
        "місто": "г.",
        "г": "г.",
        "поселок городского типа": "пгт",
        "селище міського типу": "пгт",
    }
    mapped = table.get(key)
    return mapped or normalized


def _normalize_date_for_np(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""

    for date_format in ("%d.%m.%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(normalized, date_format).strftime("%d.%m.%Y")
        except ValueError:
            continue
    return ""


def _normalize_document_datetime_for_np(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for date_format in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            parsed = datetime.strptime(normalized, date_format)
            if date_format == "%Y-%m-%d %H:%M:%S":
                return parsed.strftime("%Y-%m-%d %H:%M:%S")
            return parsed.strftime("%Y-%m-%d 00:00:00")
        except ValueError:
            continue
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _resolve_lookup_service_type(delivery_type: str) -> str:
    return "WarehouseDoors" if (delivery_type or "").strip() == "address" else "WarehouseWarehouse"
