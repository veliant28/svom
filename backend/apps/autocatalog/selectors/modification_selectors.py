from __future__ import annotations

from django.db.models import Max, Q, QuerySet
from django.db.models.functions import ExtractYear

from apps.autocatalog.models import CarMake, CarModel, CarModification


def get_autocatalog_modifications_queryset() -> QuerySet[CarModification]:
    return (
        CarModification.objects.select_related("make", "model")
        .order_by("make__name", "model__name", "year", "modification", "engine")
    )


def _complete_garage_modifications_queryset() -> QuerySet[CarModification]:
    return (
        CarModification.objects.select_related("make", "model")
        .exclude(year__isnull=True)
        .exclude(modification="")
        .exclude(capacity="")
        .exclude(engine="")
    )


def _filter_by_production_year(queryset: QuerySet[CarModification], year: int | None) -> QuerySet[CarModification]:
    if year is None:
        return queryset
    max_year = _get_global_garage_max_year()
    if max_year is not None and year > max_year:
        return queryset.none()
    return queryset.filter(
        year__lte=year,
    ).filter(
        Q(end_date_at__isnull=True) | Q(end_date_at__year__gte=year),
    )


def _get_global_garage_max_year() -> int | None:
    queryset = _complete_garage_modifications_queryset()
    max_start_year = queryset.aggregate(value=Max("year"))["value"]
    max_end_year = queryset.annotate(end_year=ExtractYear("end_date_at")).aggregate(value=Max("end_year"))["value"]
    years = [year for year in (max_start_year, max_end_year) if isinstance(year, int)]
    return max(years) if years else None


def get_autocatalog_garage_makes_queryset(*, year: int | None = None) -> QuerySet[CarMake]:
    if year is None:
        return CarMake.objects.none()

    modifications = _filter_by_production_year(_complete_garage_modifications_queryset(), year)
    return CarMake.objects.filter(modifications__in=modifications).distinct().order_by("name")


def get_autocatalog_garage_models_queryset(*, make_id: str, year: int | None = None) -> QuerySet[CarModel]:
    if not make_id:
        return CarModel.objects.none()

    modifications = _filter_by_production_year(
        _complete_garage_modifications_queryset().filter(make_id=make_id),
        year,
    )

    return (
        CarModel.objects.filter(make_id=make_id, modifications__in=modifications)
        .select_related("make")
        .distinct()
        .order_by("name")
    )


def get_autocatalog_garage_years(
    *,
    make_id: str = "",
    model_id: str = "",
    modification: str = "",
    capacity: str = "",
    engine: str = "",
) -> list[int]:
    queryset = _complete_garage_modifications_queryset()
    if make_id:
        queryset = queryset.filter(make_id=make_id)
    if model_id:
        queryset = queryset.filter(model_id=model_id)
    if modification:
        queryset = queryset.filter(modification=modification.strip())
    if capacity:
        queryset = queryset.filter(capacity=capacity.strip())
    if engine:
        queryset = queryset.filter(id=engine)

    max_year = _get_global_garage_max_year()
    if max_year is None:
        return []

    years: set[int] = set()
    for start_year, end_date in queryset.values_list("year", "end_date_at"):
        if not isinstance(start_year, int):
            continue
        end_year = end_date.year if end_date else max_year
        if end_year < start_year:
            end_year = start_year
        years.update(range(start_year, end_year + 1))

    return sorted(years, reverse=True)


def get_autocatalog_garage_modification_names(*, make_id: str, model_id: str, year: int | None) -> list[str]:
    if not make_id or not model_id:
        return []

    queryset = _complete_garage_modifications_queryset().filter(make_id=make_id, model_id=model_id)
    queryset = _filter_by_production_year(queryset, year)

    names = queryset.values_list("modification", flat=True).distinct().order_by("modification")
    return [name.strip() for name in names if isinstance(name, str) and name.strip()]


def get_autocatalog_engine_options(
    *,
    make_id: str,
    model_id: str,
    year: int | None,
    modification: str,
    capacity: str,
) -> QuerySet[CarModification]:
    if not make_id or not model_id or not modification or not capacity:
        return CarModification.objects.none()

    queryset = _complete_garage_modifications_queryset().filter(
        make_id=make_id,
        model_id=model_id,
        modification=modification.strip(),
        capacity=capacity.strip(),
    )
    queryset = _filter_by_production_year(queryset, year)

    return queryset.select_related("make", "model").order_by("-year", "engine", "hp_from", "kw_from", "id")


def get_autocatalog_garage_capacities(
    *,
    make_id: str,
    model_id: str,
    year: int | None,
    modification: str,
) -> list[str]:
    if not make_id or not model_id or not modification:
        return []

    queryset = _complete_garage_modifications_queryset().filter(
        make_id=make_id,
        model_id=model_id,
        modification=modification.strip(),
    )
    queryset = _filter_by_production_year(queryset, year)

    capacities = queryset.values_list("capacity", flat=True).distinct().order_by("capacity")
    return [value.strip() for value in capacities if isinstance(value, str) and value.strip()]
