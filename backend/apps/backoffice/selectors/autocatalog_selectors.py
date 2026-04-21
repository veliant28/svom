from __future__ import annotations

from django.db.models import Exists, OuterRef, Q, QuerySet

from apps.autocatalog.models import CarModification, UtrDetailCarMap
from apps.autocatalog.selectors import get_autocatalog_modifications_queryset


def apply_autocatalog_filters(queryset: QuerySet[CarModification], *, params) -> QuerySet[CarModification]:
    query = params.get("q", "").strip()
    make = params.get("make", "").strip()
    model = params.get("model", "").strip()
    year = params.get("year", "").strip()
    modification = params.get("modification", "").strip()
    engine = params.get("engine", "").strip()
    capacity = params.get("capacity", "").strip()
    mapped = params.get("mapped", "").strip().lower()

    if make:
        queryset = queryset.filter(make__name__icontains=make)
    if model:
        queryset = queryset.filter(model__name__icontains=model)
    if engine:
        queryset = queryset.filter(engine__icontains=engine)
    if capacity:
        queryset = queryset.filter(capacity__icontains=capacity)
    if modification:
        queryset = queryset.filter(modification__icontains=modification)
    if year:
        try:
            queryset = queryset.filter(year=int(year))
        except (TypeError, ValueError):
            pass
    if mapped in {"true", "1", "yes"}:
        mapped_rows = UtrDetailCarMap.objects.filter(car_modification_id=OuterRef("pk"))
        queryset = queryset.annotate(has_utr_map=Exists(mapped_rows))
        queryset = queryset.filter(has_utr_map=True)
    elif mapped in {"false", "0", "no"}:
        mapped_rows = UtrDetailCarMap.objects.filter(car_modification_id=OuterRef("pk"))
        queryset = queryset.annotate(has_utr_map=Exists(mapped_rows))
        queryset = queryset.filter(has_utr_map=False)

    if query:
        queryset = queryset.filter(
            Q(make__name__icontains=query)
            | Q(model__name__icontains=query)
            | Q(modification__icontains=query)
            | Q(engine__icontains=query),
        )

    return queryset


def get_autocatalog_filter_options(*, queryset: QuerySet[CarModification], params) -> dict[str, list]:
    year = params.get("year", "").strip()
    make = params.get("make", "").strip()
    model = params.get("model", "").strip()
    modification = params.get("modification", "").strip()
    capacity = params.get("capacity", "").strip()

    year_scoped = _filter_eq(queryset, year=year)
    make_scoped = _filter_eq(year_scoped, make=make)
    model_scoped = _filter_eq(make_scoped, model=model)
    modification_scoped = _filter_eq(model_scoped, modification=modification)
    capacity_scoped = _filter_eq(modification_scoped, capacity=capacity)

    has_make = bool(make)
    has_model = bool(model)
    has_modification = bool(modification)
    has_capacity = bool(capacity)

    return {
        "years": list(
            queryset.exclude(year__isnull=True).values_list("year", flat=True).distinct().order_by("-year")
        ),
        "makes": _list_distinct_strings(year_scoped, "make__name"),
        "models": _list_distinct_strings(make_scoped, "model__name") if has_make else [],
        "modifications": _list_distinct_strings(model_scoped, "modification") if has_make and has_model else [],
        "capacities": _list_distinct_strings(modification_scoped, "capacity") if has_make and has_model and has_modification else [],
        "engines": _list_distinct_strings(capacity_scoped, "engine") if has_make and has_model and has_modification and has_capacity else [],
    }


def _list_distinct_strings(queryset: QuerySet[CarModification], field_name: str) -> list[str]:
    values = queryset.values_list(field_name, flat=True).distinct().order_by(field_name)
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]


def _filter_eq(
    queryset: QuerySet[CarModification],
    *,
    year: str = "",
    make: str = "",
    model: str = "",
    modification: str = "",
    capacity: str = "",
) -> QuerySet[CarModification]:
    scoped = queryset
    if year:
        try:
            scoped = scoped.filter(year=int(year))
        except (TypeError, ValueError):
            pass
    if make:
        scoped = scoped.filter(make__name__iexact=make)
    if model:
        scoped = scoped.filter(model__name__iexact=model)
    if modification:
        scoped = scoped.filter(modification__iexact=modification)
    if capacity:
        scoped = scoped.filter(capacity__iexact=capacity)
    return scoped
