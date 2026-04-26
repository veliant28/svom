from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.autocatalog.models import UtrDetailCarMap
from apps.catalog.selectors import get_product_detail_queryset
from apps.catalog.services.product_fitment_lookup import (
    get_utr_fitment_queryset,
    parse_positive_int,
    resolve_product_utr_detail_ids,
    resolve_selected_autocatalog_vehicle,
    serialize_utr_fitment_mapping,
)


def _get_product(slug: str):
    return get_object_or_404(get_product_detail_queryset(), slug=slug)


def _manual_fitment_row(fitment) -> dict:
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

        for fitment in product.fitments.all():
            row = _manual_fitment_row(fitment)
            if row["make"]:
                makes.add(row["make"])
            if not selected_make or row["make"] == selected_make:
                if row["model"]:
                    models.add(row["model"])

        detail_ids = resolve_product_utr_detail_ids(product=product)
        if detail_ids:
            utr_maps = UtrDetailCarMap.objects.filter(utr_detail_id__in=sorted(detail_ids))
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

        selected_vehicle = resolve_selected_autocatalog_vehicle(request)
        selected_fits = False
        if selected_vehicle is not None and detail_ids:
            selected_fits = UtrDetailCarMap.objects.filter(
                utr_detail_id__in=sorted(detail_ids),
                car_modification_id=selected_vehicle.id,
            ).exists()

        return Response(
            {
                "makes": [_option(name) for name in sorted(makes)],
                "models": [_option(name) for name in sorted(models)],
                "selected_make": selected_vehicle.make_name if selected_vehicle and selected_fits else "",
                "selected_model": selected_vehicle.model_name if selected_vehicle and selected_fits else "",
                "total_fitments": product.fitments.count()
                + (UtrDetailCarMap.objects.filter(utr_detail_id__in=sorted(detail_ids)).count() if detail_ids else 0),
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

        manual_rows = []
        for fitment in product.fitments.all():
            row = _manual_fitment_row(fitment)
            if selected_make and row["make"] != selected_make:
                continue
            if selected_model and row["model"] != selected_model:
                continue
            manual_rows.append(row)

        detail_ids = resolve_product_utr_detail_ids(product=product)
        selected_vehicle = resolve_selected_autocatalog_vehicle(request)
        utr_maps = get_utr_fitment_queryset(detail_ids=detail_ids, selected_vehicle=selected_vehicle) if detail_ids else None
        if utr_maps is not None:
            if not selected_make and not selected_model and selected_vehicle is not None:
                selected_make = selected_vehicle.make_name
                selected_model = selected_vehicle.model_name
            if selected_make:
                utr_maps = utr_maps.filter(car_modification__make__name=selected_make)
            if selected_model:
                utr_maps = utr_maps.filter(car_modification__model__name=selected_model)

        utr_count = utr_maps.count() if utr_maps is not None else 0
        total_count = len(manual_rows) + utr_count
        results: list[dict] = []

        manual_slice = manual_rows[offset : offset + limit]
        results.extend(manual_slice)

        remaining_limit = limit - len(results)
        utr_offset = max(offset - len(manual_rows), 0)
        if remaining_limit > 0 and utr_maps is not None:
            for mapping in utr_maps[utr_offset : utr_offset + remaining_limit]:
                results.append(serialize_utr_fitment_mapping(mapping))

        return Response(
            {
                "count": total_count,
                "next_offset": offset + limit if offset + limit < total_count else None,
                "results": results,
            }
        )
