from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.compatibility.models import ProductFitment
from apps.catalog.selectors import get_product_detail_queryset
from apps.catalog.services.product_fitment_lookup import (
    get_autodb_fitment_queryset,
    get_utr_fitment_queryset,
    is_autodb_fitment_provider,
    parse_positive_int,
    resolve_product_utr_detail_ids,
    resolve_selected_autocatalog_vehicle,
    serialize_autodb_fitment_mapping,
    serialize_utr_fitment_mapping,
)


def _get_product(slug: str):
    return get_object_or_404(get_product_detail_queryset(), slug=slug)


def _manual_fitment_row(fitment) -> dict:
    if fitment.modification_id is None or str(fitment.source or "") == ProductFitment.SOURCE_AUTODB_PRO:
        return {}
    modification = fitment.modification
    engine = modification.engine
    generation = engine.generation
    model = generation.model
    make = model.make
    return {
        "id": str(fitment.id),
        "make": str(make.name),
        "model": str(model.name),
        "generation": str(generation.name),
        "engine": str(engine.name),
        "modification": str(modification.name),
        "note": str(fitment.note or ""),
        "is_exact": bool(fitment.is_exact),
    }


def _option(name: str) -> dict:
    return {"value": name, "label": name}


class ProductFitmentOptionsAPIView(APIView):
    def get(self, request, slug: str):
        product = _get_product(slug)
        selected_make = str(request.query_params.get("make") or "").strip()
        makes: set[str] = set()
        models: set[str] = set()
        using_autodb = is_autodb_fitment_provider()

        manual_count = 0
        for fitment in product.fitments.all():
            row = _manual_fitment_row(fitment)
            if not row:
                continue
            manual_count += 1
            if row["make"]:
                makes.add(row["make"])
            if not selected_make or row["make"] == selected_make:
                if row["model"]:
                    models.add(row["model"])

        selected_vehicle = resolve_selected_autocatalog_vehicle(request)
        selected_fits = False
        external_count = 0

        if using_autodb:
            autodb_maps = get_autodb_fitment_queryset(product=product, selected_vehicle=selected_vehicle)
            external_count = autodb_maps.count()
            makes.update(
                str(name)
                for name in autodb_maps.values_list("model__manufacturer__description", flat=True)
                .distinct()
                .order_by("model__manufacturer__description")
                if name
            )
            model_queryset = autodb_maps
            if selected_make:
                model_queryset = model_queryset.filter(model__manufacturer__description=selected_make)
            models.update(
                str(name)
                for name in model_queryset.values_list("model__description", flat=True)
                .distinct()
                .order_by("model__description")
                if name
            )
            if selected_vehicle is not None:
                selected_fits = autodb_maps.filter(
                    model__manufacturer__description=selected_vehicle.make_name,
                    model__description=selected_vehicle.model_name,
                ).exists()
        else:
            detail_ids = resolve_product_utr_detail_ids(product=product)
            if detail_ids:
                utr_maps = get_utr_fitment_queryset(detail_ids=detail_ids, selected_vehicle=selected_vehicle)
                external_count = utr_maps.count()
                makes.update(
                    str(name)
                    for name in utr_maps.values_list("car_modification__make__name", flat=True)
                    .distinct()
                    .order_by("car_modification__make__name")
                    if name
                )
                model_queryset = utr_maps
                if selected_make:
                    model_queryset = model_queryset.filter(car_modification__make__name=selected_make)
                models.update(
                    str(name)
                    for name in model_queryset.values_list("car_modification__model__name", flat=True)
                    .distinct()
                    .order_by("car_modification__model__name")
                    if name
                )
                if selected_vehicle is not None:
                    selected_fits = utr_maps.filter(car_modification_id=selected_vehicle.id).exists()

        return Response(
            {
                "makes": [_option(name) for name in sorted(makes)],
                "models": [_option(name) for name in sorted(models)],
                "selected_make": selected_vehicle.make_name if selected_vehicle and selected_fits else "",
                "selected_model": selected_vehicle.model_name if selected_vehicle and selected_fits else "",
                "total_fitments": manual_count + external_count,
            }
        )


class ProductFitmentRowsAPIView(APIView):
    max_limit = 500
    default_limit = 120

    def get(self, request, slug: str):
        product = _get_product(slug)
        selected_make = str(request.query_params.get("make") or "").strip()
        selected_model = str(request.query_params.get("model") or "").strip()
        limit = min(parse_positive_int(request.query_params.get("limit")) or self.default_limit, self.max_limit)
        offset = parse_positive_int(request.query_params.get("offset")) or 0
        using_autodb = is_autodb_fitment_provider()

        manual_rows = []
        for fitment in product.fitments.all():
            row = _manual_fitment_row(fitment)
            if not row:
                continue
            if selected_make and row["make"] != selected_make:
                continue
            if selected_model and row["model"] != selected_model:
                continue
            manual_rows.append(row)

        selected_vehicle = resolve_selected_autocatalog_vehicle(request)
        external_maps = None
        if using_autodb:
            external_maps = get_autodb_fitment_queryset(product=product, selected_vehicle=selected_vehicle)
            if selected_vehicle is not None and not selected_make and not selected_model:
                selected_make = selected_vehicle.make_name
                selected_model = selected_vehicle.model_name
            if selected_make:
                external_maps = external_maps.filter(model__manufacturer__description=selected_make)
            if selected_model:
                external_maps = external_maps.filter(model__description=selected_model)
        else:
            detail_ids = resolve_product_utr_detail_ids(product=product)
            if detail_ids:
                external_maps = get_utr_fitment_queryset(detail_ids=detail_ids, selected_vehicle=selected_vehicle)
                if selected_vehicle is not None and not selected_make and not selected_model:
                    selected_make = selected_vehicle.make_name
                    selected_model = selected_vehicle.model_name
                if selected_make:
                    external_maps = external_maps.filter(car_modification__make__name=selected_make)
                if selected_model:
                    external_maps = external_maps.filter(car_modification__model__name=selected_model)

        external_count = external_maps.count() if external_maps is not None else 0
        total_count = len(manual_rows) + external_count
        results: list[dict] = []

        manual_slice = manual_rows[offset : offset + limit]
        results.extend(manual_slice)

        remaining_limit = limit - len(results)
        utr_offset = max(offset - len(manual_rows), 0)
        if remaining_limit > 0 and external_maps is not None:
            for mapping in external_maps[utr_offset : utr_offset + remaining_limit]:
                if using_autodb:
                    results.append(serialize_autodb_fitment_mapping(mapping))
                else:
                    results.append(serialize_utr_fitment_mapping(mapping))

        return Response(
            {
                "count": total_count,
                "next_offset": offset + limit if offset + limit < total_count else None,
                "results": results,
            }
        )
