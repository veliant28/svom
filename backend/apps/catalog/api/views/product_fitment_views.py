from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.catalog.services.product_fitment_lookup import (
    get_public_autodb_fitment_entries,
    _linkage_type_key,
    parse_positive_int,
    resolve_public_autodb_vehicle_map_by_entries,
    resolve_selected_passanger_car_id,
    resolve_selected_autodb_vehicle_display,
    serialize_autodb_fitment_mapping_from_selector,
    serialize_autodb_fitment_fallback_row,
)


def _get_product(slug: str):
    queryset = Product.objects.filter(is_active=True).only(
        "id",
        "slug",
        "article",
        "category_id",
        "display_brand_name",
        "normalized_brand",
        "autodb_supplier_id",
        "autodb_supplier_name",
        "autodb_article_number",
        "autodb_article_key",
    )
    return get_object_or_404(queryset, slug=slug)


def _option(name: str) -> dict:
    return {"value": name, "label": name}


def _vehicle_option(vehicle_id: int, label: str) -> dict:
    return {"value": str(vehicle_id), "label": label}


def _collect_fitment_rows(*, product: Product, selected_vehicle_display: dict | None) -> list[dict]:
    fitment_entries = get_public_autodb_fitment_entries(product=product, include_commercial=True)
    fitment_vehicle_map = resolve_public_autodb_vehicle_map_by_entries(fitment_entries=fitment_entries)

    rows: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for entry in fitment_entries:
        vehicle_id = int(entry.get("vehicle_id") or 0)
        linkage_type = str(entry.get("linkage_type") or "")
        if vehicle_id <= 0:
            continue
        key = (_linkage_type_key(linkage_type), vehicle_id)
        if key in seen:
            continue
        seen.add(key)

        vehicle = fitment_vehicle_map.get(key)
        if vehicle is not None:
            row = serialize_autodb_fitment_mapping_from_selector(vehicle)
        else:
            row = serialize_autodb_fitment_fallback_row(
                passanger_car_id=vehicle_id,
                selected_vehicle=selected_vehicle_display,
                linkage_type=linkage_type,
            )
            row = {
                **row,
                "manufacturer_id": 0,
                "model_id": 0,
            }
        rows.append(row)
    return rows


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
        selected_vehicle_display = resolve_selected_autodb_vehicle_display(request)
        vehicle_rows = _collect_fitment_rows(product=product, selected_vehicle_display=selected_vehicle_display)
        total_fitments = len(vehicle_rows)
        selected_vehicle_id = int(selected_vehicle_display.get("vehicle_id", 0)) if selected_vehicle_display else 0
        if selected_vehicle_id <= 0:
            selected_vehicle_id = int(resolve_selected_passanger_car_id(request) or 0)

        selected_vehicle_row = None
        if selected_vehicle_id > 0:
            selected_vehicle_row = next(
                (row for row in vehicle_rows if int(row.get("vehicle_id") or 0) == selected_vehicle_id),
                None,
            )

        if not selected_make and selected_vehicle_row is not None:
            selected_make = str(selected_vehicle_row.get("make") or "").strip()
        if not selected_model and selected_vehicle_row is not None:
            selected_model = str(selected_vehicle_row.get("model") or "").strip()

        if selected_modification and not selected_make and not selected_model:
            selected_modification_id = parse_positive_int(selected_modification)
            if selected_modification_id:
                selected_row = next(
                    (row for row in vehicle_rows if int(row.get("vehicle_id") or 0) == selected_modification_id),
                    None,
                )
                if selected_row is not None:
                    selected_make = str(selected_row.get("make") or "").strip()
                    selected_model = str(selected_row.get("model") or "").strip()

        for row in vehicle_rows:
            make_name = str(row.get("make") or "").strip()
            if make_name:
                makes.add(make_name)

        model_rows = vehicle_rows
        if selected_make_id:
            model_rows = [row for row in model_rows if int(row.get("manufacturer_id") or 0) == selected_make_id]
        if selected_make:
            model_rows = [row for row in model_rows if str(row.get("make") or "").strip() == selected_make]
        for row in model_rows:
            model_name = str(row.get("model") or "").strip()
            if model_name:
                models.add(model_name)

        should_load_modifications = bool(
            selected_make
            or selected_model
            or selected_make_id
            or selected_model_id
            or selected_modification
        )
        if should_load_modifications:
            filtered_rows = vehicle_rows
            if selected_make_id:
                filtered_rows = [row for row in filtered_rows if int(row.get("manufacturer_id") or 0) == selected_make_id]
            if selected_make:
                filtered_rows = [row for row in filtered_rows if str(row.get("make") or "").strip() == selected_make]
            if selected_model_id:
                filtered_rows = [row for row in filtered_rows if int(row.get("model_id") or 0) == selected_model_id]
            if selected_model:
                filtered_rows = [row for row in filtered_rows if str(row.get("model") or "").strip() == selected_model]

            seen_vehicle_ids: set[int] = set()
            for row in filtered_rows[:500]:
                vehicle_id = int(row.get("vehicle_id") or 0)
                if vehicle_id <= 0 or vehicle_id in seen_vehicle_ids:
                    continue
                seen_vehicle_ids.add(vehicle_id)
                modifications.append(_vehicle_option(vehicle_id, str(row.get("label") or f"Автомобиль #{vehicle_id}")))

        response_selected_make = selected_make if selected_make in makes else ""
        response_selected_model = selected_model if selected_model in models else ""
        response_selected_modification = ""
        if selected_modification:
            response_selected_modification = selected_modification
        elif selected_vehicle_row is not None:
            response_selected_modification = str(int(selected_vehicle_row.get("vehicle_id") or 0))

        return Response(
            {
                "makes": [_option(name) for name in sorted(makes)],
                "models": [_option(name) for name in sorted(models)],
                "selected_make": response_selected_make,
                "selected_model": response_selected_model,
                "selected_modification": response_selected_modification,
                "modifications": modifications,
                "total_fitments": total_fitments,
            }
        )


class ProductFitmentRowsAPIView(APIView):
    max_limit = 300
    default_limit = 10

    def get(self, request, slug: str):
        product = _get_product(slug)
        selected_make = str(request.query_params.get("make") or "").strip()
        selected_model = str(request.query_params.get("model") or "").strip()
        selected_make_id = parse_positive_int(
            request.query_params.get("make_id") or request.query_params.get("manufacturer_id")
        )
        selected_model_id = parse_positive_int(request.query_params.get("model_id"))
        selected_modification = str(request.query_params.get("modification") or "").strip()
        limit = min(parse_positive_int(request.query_params.get("limit")) or self.default_limit, self.max_limit)
        offset = parse_positive_int(request.query_params.get("offset")) or 0

        selected_vehicle_display = resolve_selected_autodb_vehicle_display(request)
        selected_vehicle_id = int(selected_vehicle_display.get("vehicle_id", 0)) if selected_vehicle_display else 0
        vehicle_rows = _collect_fitment_rows(product=product, selected_vehicle_display=selected_vehicle_display)
        selected_vehicle_row = None
        if selected_vehicle_id > 0:
            selected_vehicle_row = next(
                (row for row in vehicle_rows if int(row.get("vehicle_id") or 0) == selected_vehicle_id),
                None,
            )
        if selected_vehicle_row is not None and not selected_make and not selected_model and not selected_modification:
            selected_make = str(selected_vehicle_row.get("make") or "").strip()
            selected_model = str(selected_vehicle_row.get("model") or "").strip()

        filtered_rows = vehicle_rows
        if selected_make_id:
            filtered_rows = [row for row in filtered_rows if int(row.get("manufacturer_id") or 0) == selected_make_id]
        if selected_make:
            filtered_rows = [row for row in filtered_rows if str(row.get("make") or "").strip() == selected_make]
        if selected_model_id:
            filtered_rows = [row for row in filtered_rows if int(row.get("model_id") or 0) == selected_model_id]
        if selected_model:
            filtered_rows = [row for row in filtered_rows if str(row.get("model") or "").strip() == selected_model]
        if selected_modification:
            selected_modification_id = parse_positive_int(selected_modification)
            if selected_modification_id:
                filtered_rows = [row for row in filtered_rows if int(row.get("vehicle_id") or 0) == selected_modification_id]

        total_count = len(filtered_rows)
        results = filtered_rows[offset : offset + limit]

        return Response(
            {
                "count": total_count,
                "next_offset": offset + limit if offset + limit < total_count else None,
                "results": results,
            }
        )
