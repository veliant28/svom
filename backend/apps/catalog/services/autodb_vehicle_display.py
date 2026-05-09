from __future__ import annotations

from typing import Mapping

from apps.users.models import GarageVehicle


def _clean(value: object) -> str:
    return str(value or "").strip()


def _compact_spaces(value: str) -> str:
    return " ".join(value.split())


def _render_years(start_year: int | None, end_year: int | None, fallback: str = "") -> str:
    if start_year or end_year:
        start_label = str(start_year) if start_year else "?"
        end_label = str(end_year) if end_year else "..."
        return f"{start_label}–{end_label}"
    return _compact_spaces(fallback)


def _render_engine(*, capacity: str = "", fuel: str = "", power_kw: int | None = None, power_hp: int | None = None, code: str = "") -> str:
    parts: list[str] = []
    if _clean(capacity):
        parts.append(_clean(capacity))
    if _clean(fuel):
        parts.append(_clean(fuel))

    power_parts: list[str] = []
    if power_kw:
        power_parts.append(f"{power_kw} kW")
    if power_hp:
        power_parts.append(f"{power_hp} hp")
    if power_parts:
        parts.append(" / ".join(power_parts))

    if _clean(code):
        parts.append(_clean(code))

    return " · ".join(parts)


def build_autodb_passanger_car_label(passanger_car: Mapping[str, object]) -> dict[str, str | int]:
    vehicle_id = int(passanger_car.get("vehicle_id") or passanger_car.get("id") or 0)
    make = _clean(passanger_car.get("make"))
    model_name = _clean(passanger_car.get("model"))
    modification = _clean(passanger_car.get("modification") or passanger_car.get("name") or passanger_car.get("description"))
    years = _clean(passanger_car.get("years"))
    if not years:
        years = _render_years(
            passanger_car.get("year_from") if isinstance(passanger_car.get("year_from"), int) else None,
            passanger_car.get("year_to") if isinstance(passanger_car.get("year_to"), int) else None,
            _clean(passanger_car.get("construction_interval") or passanger_car.get("raw_construction_interval")),
        )
    engine = _render_engine(
        capacity=_clean(passanger_car.get("engine_capacity")),
        fuel=_clean(passanger_car.get("fuel_type")),
        power_kw=passanger_car.get("power_kw") if isinstance(passanger_car.get("power_kw"), int) else None,
        power_hp=passanger_car.get("power_hp") if isinstance(passanger_car.get("power_hp"), int) else None,
        code=_clean(passanger_car.get("engine_code")),
    )
    body = _clean(passanger_car.get("body") or passanger_car.get("body_type"))

    label_parts = [value for value in [make, model_name, modification] if value]
    label = _compact_spaces(" ".join(label_parts))
    if years:
        label = f"{label} ({years})" if label else years
    if not label:
        label = f"Автомобиль #{vehicle_id}" if vehicle_id else "Автомобиль"

    return {
        "vehicle_id": vehicle_id,
        "make": make,
        "model": model_name,
        "modification": modification,
        "years": years,
        "engine": engine,
        "body": body,
        "label": label,
        "subtitle": engine,
    }


def build_autodb_garage_vehicle_label(*, garage_vehicle: GarageVehicle, passanger_car_id: int | None = None) -> dict[str, str | int]:
    make = _clean(getattr(getattr(garage_vehicle, "make", None), "name", ""))
    model_name = _clean(getattr(getattr(garage_vehicle, "model", None), "name", ""))
    modification = _clean(garage_vehicle.autodb_modification or garage_vehicle.nickname)
    years = str(garage_vehicle.year or "")
    engine = _render_engine(
        capacity="",
        fuel="",
        power_kw=garage_vehicle.autodb_power_kw,
        power_hp=garage_vehicle.autodb_power_hp,
        code=_clean(garage_vehicle.autodb_engine),
    )

    label = _clean(garage_vehicle.autodb_vehicle_label)
    if not label:
        label_parts = [value for value in [make, model_name, modification] if value]
        label = _compact_spaces(" ".join(label_parts))
        if years:
            label = f"{label} ({years})" if label else years
    if not label:
        fallback_id = passanger_car_id or garage_vehicle.autodb_passanger_car_id
        label = f"Автомобиль #{fallback_id}" if fallback_id else "Автомобиль"

    vehicle_id = passanger_car_id or garage_vehicle.autodb_passanger_car_id
    return {
        "vehicle_id": int(vehicle_id) if vehicle_id else 0,
        "make": make,
        "model": model_name,
        "modification": modification,
        "years": years,
        "engine": engine,
        "body": "",
        "label": label,
        "subtitle": engine,
    }
