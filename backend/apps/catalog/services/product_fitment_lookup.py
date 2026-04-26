from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Case, IntegerField, OuterRef, Subquery, Value, When

from apps.autocatalog.models import CarModification, UtrArticleDetailMap, UtrDetailCarMap
from apps.catalog.models import Product
from apps.supplier_imports.models import SupplierRawOffer
from apps.users.models import GarageVehicle


@dataclass(frozen=True)
class SelectedAutocatalogVehicle:
    id: int
    make_id: int
    make_name: str
    model_id: int
    model_name: str


def parse_positive_int(value) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def resolve_selected_car_modification_id(request) -> int | None:
    if request is None:
        return None

    explicit_car_modification_id = parse_positive_int(request.query_params.get("car_modification"))
    if explicit_car_modification_id:
        return explicit_car_modification_id

    garage_vehicle_id = str(request.query_params.get("garage_vehicle") or "").strip()
    if not garage_vehicle_id:
        return None

    garage_vehicle = GarageVehicle.objects.filter(id=garage_vehicle_id).values("car_modification_id").first()
    return parse_positive_int(garage_vehicle.get("car_modification_id")) if garage_vehicle else None


def resolve_selected_autocatalog_vehicle(request) -> SelectedAutocatalogVehicle | None:
    car_modification_id = resolve_selected_car_modification_id(request)
    if not car_modification_id:
        return None

    row = (
        CarModification.objects.filter(id=car_modification_id)
        .select_related("make", "model")
        .values("id", "make_id", "make__name", "model_id", "model__name")
        .first()
    )
    if not row:
        return None

    return SelectedAutocatalogVehicle(
        id=int(row["id"]),
        make_id=int(row["make_id"]),
        make_name=str(row["make__name"]),
        model_id=int(row["model_id"]),
        model_name=str(row["model__name"]),
    )


def resolve_product_utr_detail_ids(*, product: Product) -> set[str]:
    detail_ids: set[str] = set()
    product_detail_id = str(product.utr_detail_id or "").strip()
    if product_detail_id:
        detail_ids.add(product_detail_id)

    mapped_detail_ids_qs = (
        SupplierRawOffer.objects.filter(
            matched_product_id=product.id,
            supplier__code="utr",
        )
        .annotate(
            map_detail_id=Subquery(
                UtrArticleDetailMap.objects.filter(
                    normalized_article=OuterRef("normalized_article"),
                    normalized_brand=OuterRef("normalized_brand"),
                )
                .exclude(utr_detail_id="")
                .values("utr_detail_id")[:1]
            )
        )
        .exclude(map_detail_id__isnull=True)
        .values_list("map_detail_id", flat=True)
        .distinct()
    )
    for detail_id in mapped_detail_ids_qs:
        normalized = str(detail_id or "").strip()
        if normalized:
            detail_ids.add(normalized)
    return detail_ids


def build_autocatalog_generation(car) -> str:
    if car.start_date_at or car.end_date_at:
        start_label = str(car.start_date_at.year) if car.start_date_at else "?"
        end_label = str(car.end_date_at.year) if car.end_date_at else "..."
        return f"{start_label}-{end_label}"
    if car.year:
        return str(car.year)
    return ""


def serialize_utr_fitment_mapping(mapping: UtrDetailCarMap) -> dict:
    car = mapping.car_modification
    return {
        "id": f"utr-{mapping.utr_detail_id}-{car.id}",
        "make": str(car.make.name),
        "model": str(car.model.name),
        "generation": build_autocatalog_generation(car),
        "engine": str(car.engine or ""),
        "modification": str(car.modification or ""),
        "note": "UTR applicability",
        "is_exact": False,
    }


def get_utr_fitment_queryset(*, detail_ids: set[str], selected_vehicle: SelectedAutocatalogVehicle | None = None):
    queryset = UtrDetailCarMap.objects.filter(utr_detail_id__in=sorted(detail_ids)).select_related(
        "car_modification",
        "car_modification__make",
        "car_modification__model",
    )

    if selected_vehicle is not None:
        queryset = queryset.annotate(
            selected_order=Case(
                When(car_modification_id=selected_vehicle.id, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            selected_model_order=Case(
                When(
                    car_modification__make_id=selected_vehicle.make_id,
                    car_modification__model_id=selected_vehicle.model_id,
                    then=Value(0),
                ),
                default=Value(1),
                output_field=IntegerField(),
            ),
        ).order_by(
            "selected_order",
            "selected_model_order",
            "utr_detail_id",
            "car_modification__make__name",
            "car_modification__model__name",
            "car_modification__year",
            "car_modification__modification",
            "car_modification__engine",
            "car_modification_id",
        )
    else:
        queryset = queryset.order_by(
            "utr_detail_id",
            "car_modification__make__name",
            "car_modification__model__name",
            "car_modification__year",
            "car_modification__modification",
            "car_modification__engine",
            "car_modification_id",
        )

    return queryset
