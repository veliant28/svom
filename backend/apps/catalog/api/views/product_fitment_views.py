from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.selectors import get_product_detail_queryset
from apps.catalog.services.product_fitment_lookup import (
    get_autodb_fitment_queryset,
    get_public_autodb_fitment_entries,
    LINKAGE_TYPE_PASSENGER_CAR,
    _linkage_type_key,
    parse_positive_int,
    resolve_public_autodb_vehicle_map_by_entries,
    resolve_selected_passanger_car_id,
    resolve_selected_autodb_vehicle_display,
    resolve_selected_autocatalog_vehicle,
    serialize_autodb_fitment_mapping,
    serialize_autodb_fitment_mapping_from_selector,
    serialize_autodb_fitment_fallback_row,
)


def _get_product(slug: str):
    return get_object_or_404(get_product_detail_queryset(), slug=slug)


def _option(name: str) -> dict:
    return {"value": name, "label": name}


def _vehicle_option(vehicle_id: int, label: str) -> dict:
    return {"value": str(vehicle_id), "label": label}


class ProductFitmentOptionsAPIView(APIView):
    def get(self, request, slug: str):
        product = _get_product(slug)
        selected_make = str(request.query_params.get("make") or "").strip()
        selected_model = str(request.query_params.get("model") or "").strip()
        selected_make_id = parse_positive_int(
            request.query_params.get("make_id") or request.query_params.get("manufacturer_id")
        )
        selected_model_id = parse_positive_int(request.query_params.get("model_id"))
        selected_modification = str(request.query_params.get("modification") or "").strip()
        makes: set[str] = set()
        models: set[str] = set()
        modifications: list[dict] = []

        selected_vehicle = resolve_selected_autocatalog_vehicle(request)
        selected_vehicle_display = resolve_selected_autodb_vehicle_display(request)
        selected_fits = False
        autodb_maps = get_autodb_fitment_queryset(product=product, selected_vehicle=selected_vehicle)
        external_count = len(autodb_maps)
        if external_count == 0:
            fitment_entries = get_public_autodb_fitment_entries(product=product, include_commercial=True)
            fitment_vehicle_map = resolve_public_autodb_vehicle_map_by_entries(fitment_entries=fitment_entries)
            selected_vehicle_id = int(selected_vehicle_display.get("vehicle_id", 0)) if selected_vehicle_display else 0
            if selected_vehicle_id <= 0:
                selected_vehicle_id = int(resolve_selected_passanger_car_id(request) or 0)
            passenger_fitment_ids = {
                int(item["vehicle_id"])
                for item in fitment_entries
                if _linkage_type_key(str(item.get("linkage_type") or "")) == _linkage_type_key(LINKAGE_TYPE_PASSENGER_CAR)
                and int(item["vehicle_id"]) > 0
            }
            selected_vehicle_fits = selected_vehicle_id > 0 and selected_vehicle_id in passenger_fitment_ids

            vehicle_rows: list[dict] = []
            for entry in fitment_entries:
                vehicle_id = int(entry.get("vehicle_id") or 0)
                linkage_type = str(entry.get("linkage_type") or "")
                if vehicle_id <= 0:
                    continue
                vehicle = fitment_vehicle_map.get((_linkage_type_key(linkage_type), vehicle_id))
                if vehicle is None:
                    vehicle = serialize_autodb_fitment_fallback_row(
                        passanger_car_id=vehicle_id,
                        selected_vehicle=selected_vehicle_display,
                        linkage_type=linkage_type,
                    )
                    vehicle = {
                        "vehicle_id": int(vehicle_id),
                        "make": str(vehicle.get("make") or ""),
                        "model": str(vehicle.get("model") or ""),
                        "modification": str(vehicle.get("modification") or ""),
                        "label": str(vehicle.get("label") or f"Автомобиль #{vehicle_id}"),
                        "model_id": 0,
                        "manufacturer_id": 0,
                    }
                vehicle_rows.append(
                    {
                        "vehicle_id": int(vehicle.get("vehicle_id") or 0),
                        "make": str(vehicle.get("make") or ""),
                        "model": str(vehicle.get("model") or ""),
                        "modification": str(vehicle.get("modification") or ""),
                        "label": str(vehicle.get("label") or ""),
                        "model_id": int(vehicle.get("model_id") or 0),
                        "manufacturer_id": int(vehicle.get("manufacturer_id") or 0),
                    }
                )

            for vehicle in vehicle_rows:
                make_name = str(vehicle.get("make") or "").strip()
                if make_name:
                    makes.add(make_name)

            filtered_model_rows = vehicle_rows
            if selected_make_id:
                filtered_model_rows = [
                    row for row in filtered_model_rows if int(row.get("manufacturer_id") or 0) == selected_make_id
                ]
            if selected_make:
                filtered_model_rows = [
                    row for row in filtered_model_rows if str(row.get("make") or "").strip() == selected_make
                ]
            if selected_model_id:
                filtered_model_rows = [
                    row for row in filtered_model_rows if int(row.get("model_id") or 0) == selected_model_id
                ]
            for vehicle in filtered_model_rows:
                model_name = str(vehicle.get("model") or "").strip()
                if model_name:
                    models.add(model_name)

            filtered_rows = vehicle_rows
            if selected_make_id:
                filtered_rows = [row for row in filtered_rows if int(row.get("manufacturer_id") or 0) == selected_make_id]
            if selected_make:
                filtered_rows = [row for row in filtered_rows if str(row.get("make") or "").strip() == selected_make]
            if selected_model_id:
                filtered_rows = [row for row in filtered_rows if int(row.get("model_id") or 0) == selected_model_id]
            if selected_model:
                filtered_rows = [row for row in filtered_rows if str(row.get("model") or "").strip() == selected_model]
            for row in filtered_rows[:250]:
                vehicle_id = int(row.get("vehicle_id") or 0)
                label = str(row.get("label") or "").strip()
                if vehicle_id > 0 and label:
                    modifications.append(_vehicle_option(vehicle_id, label))

            if selected_vehicle_fits:
                selected_vehicle_row = next(
                    (row for row in vehicle_rows if int(row.get("vehicle_id") or 0) == selected_vehicle_id),
                    None,
                )
                response_make = str(selected_vehicle_row.get("make") or "") if selected_vehicle_row else ""
                response_model = str(selected_vehicle_row.get("model") or "") if selected_vehicle_row else ""
                response_modification = str(selected_vehicle_id)
            else:
                response_make = ""
                response_model = ""
                response_modification = ""

            return Response(
                {
                    "makes": [_option(name) for name in sorted(makes)],
                    "models": [_option(name) for name in sorted(models)],
                    "modifications": modifications,
                    "selected_make": response_make,
                    "selected_model": response_model,
                    "selected_modification": response_modification,
                    "total_fitments": len(vehicle_rows),
                }
            )

        vehicle_rows: list[dict] = [serialize_autodb_fitment_mapping(mapping) for mapping in autodb_maps]
        for row in vehicle_rows:
            make_name = str(row.get("make") or "").strip()
            if make_name:
                makes.add(make_name)
        model_rows = vehicle_rows
        if selected_make:
            model_rows = [row for row in model_rows if str(row.get("make") or "").strip() == selected_make]
        if selected_make_id:
            model_rows = [row for row in model_rows if int(row.get("manufacturer_id") or 0) == selected_make_id]
        if selected_model_id:
            model_rows = [row for row in model_rows if int(row.get("model_id") or 0) == selected_model_id]
        for row in model_rows:
            model_name = str(row.get("model") or "").strip()
            if model_name:
                models.add(model_name)

        if selected_vehicle is not None:
            selected_fits = any(
                str(row.get("make") or "").strip() == selected_vehicle.make_name
                and str(row.get("model") or "").strip() == selected_vehicle.model_name
                for row in vehicle_rows
            )

        filtered_rows = vehicle_rows
        if selected_make:
            filtered_rows = [row for row in filtered_rows if str(row.get("make") or "").strip() == selected_make]
        if selected_make_id:
            filtered_rows = [row for row in filtered_rows if int(row.get("manufacturer_id") or 0) == selected_make_id]
        if selected_model_id:
            filtered_rows = [row for row in filtered_rows if int(row.get("model_id") or 0) == selected_model_id]
        if selected_model:
            filtered_rows = [row for row in filtered_rows if str(row.get("model") or "").strip() == selected_model]
        seen_vehicle_ids: set[int] = set()
        for row in filtered_rows[:250]:
            vehicle_id = int(row.get("vehicle_id") or 0)
            if vehicle_id <= 0 or vehicle_id in seen_vehicle_ids:
                continue
            seen_vehicle_ids.add(vehicle_id)
            modifications.append(_vehicle_option(vehicle_id, str(row.get("label") or f"Автомобиль #{vehicle_id}")))

        return Response(
            {
                "makes": [_option(name) for name in sorted(makes)],
                "models": [_option(name) for name in sorted(models)],
                "selected_make": selected_vehicle.make_name if selected_vehicle and selected_fits else "",
                "selected_model": selected_vehicle.model_name if selected_vehicle and selected_fits else "",
                "selected_modification": (
                    selected_modification
                    or (str(selected_vehicle.id) if selected_vehicle and selected_fits else "")
                ),
                "modifications": modifications,
                "total_fitments": external_count,
            }
        )


class ProductFitmentRowsAPIView(APIView):
    max_limit = 500
    default_limit = 120

    def get(self, request, slug: str):
        product = _get_product(slug)
        selected_make = str(request.query_params.get("make") or "").strip()
        selected_model = str(request.query_params.get("model") or "").strip()
        selected_modification = str(request.query_params.get("modification") or "").strip()
        limit = min(parse_positive_int(request.query_params.get("limit")) or self.default_limit, self.max_limit)
        offset = parse_positive_int(request.query_params.get("offset")) or 0

        selected_vehicle = resolve_selected_autocatalog_vehicle(request)
        selected_vehicle_display = resolve_selected_autodb_vehicle_display(request)
        external_maps = get_autodb_fitment_queryset(product=product, selected_vehicle=selected_vehicle)
        if selected_vehicle is not None and not selected_make and not selected_model:
            selected_make = selected_vehicle.make_name
            selected_model = selected_vehicle.model_name
        mapped_rows = [serialize_autodb_fitment_mapping(mapping) for mapping in external_maps]
        if selected_make:
            mapped_rows = [row for row in mapped_rows if str(row.get("make") or "").strip() == selected_make]
        if selected_model:
            mapped_rows = [row for row in mapped_rows if str(row.get("model") or "").strip() == selected_model]
        if selected_modification:
            selected_modification_id = parse_positive_int(selected_modification)
            if selected_modification_id:
                mapped_rows = [row for row in mapped_rows if int(row.get("vehicle_id") or 0) == selected_modification_id]

        external_count = len(mapped_rows)
        results: list[dict] = []
        if external_count:
            results.extend(mapped_rows[offset : offset + limit])
            total_count = external_count
        else:
            fitment_entries = get_public_autodb_fitment_entries(product=product, include_commercial=True)
            fitment_vehicle_map = resolve_public_autodb_vehicle_map_by_entries(fitment_entries=fitment_entries)
            filtered_entries = [
                item for item in fitment_entries
                if int(item.get("vehicle_id") or 0) > 0
            ]
            selected_vehicle_id = int(selected_vehicle_display.get("vehicle_id", 0)) if selected_vehicle_display else 0
            if selected_modification:
                selected_modification_id = parse_positive_int(selected_modification)
                if selected_modification_id:
                    filtered_entries = [
                        item for item in filtered_entries
                        if int(item.get("vehicle_id") or 0) == selected_modification_id
                    ]
            if selected_make:
                filtered_entries = [
                    item for item in filtered_entries
                    if str(
                        (
                            fitment_vehicle_map.get(
                                (_linkage_type_key(str(item.get("linkage_type") or "")), int(item.get("vehicle_id") or 0))
                            )
                            or {}
                        ).get("make")
                        or ""
                    ).strip()
                    == selected_make
                ]
            if selected_model:
                filtered_entries = [
                    item for item in filtered_entries
                    if str(
                        (
                            fitment_vehicle_map.get(
                                (_linkage_type_key(str(item.get("linkage_type") or "")), int(item.get("vehicle_id") or 0))
                            )
                            or {}
                        ).get("model")
                        or ""
                    ).strip()
                    == selected_model
                ]
            if (
                selected_vehicle_id > 0
                and not selected_make
                and not selected_model
                and not selected_modification
            ):
                filtered_entries = [
                    item for item in filtered_entries
                    if int(item.get("vehicle_id") or 0) == selected_vehicle_id
                ]

            total_count = len(filtered_entries)
            for entry in filtered_entries[offset : offset + limit]:
                passanger_car_id = int(entry.get("vehicle_id") or 0)
                linkage_type = str(entry.get("linkage_type") or "")
                vehicle = fitment_vehicle_map.get((_linkage_type_key(linkage_type), passanger_car_id))
                if vehicle is not None:
                    results.append(serialize_autodb_fitment_mapping_from_selector(vehicle))
                    continue
                results.append(
                    serialize_autodb_fitment_fallback_row(
                        passanger_car_id=passanger_car_id,
                        selected_vehicle=selected_vehicle_display,
                        linkage_type=linkage_type,
                    )
                )

        return Response(
            {
                "count": total_count,
                "next_offset": offset + limit if offset + limit < total_count else None,
                "results": results,
            }
        )
