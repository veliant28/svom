from __future__ import annotations

from django.db.models import QuerySet

from apps.autocatalog.models import CarMake, CarModel, CarModification, UtrDetailCarMap


def get_autocatalog_modifications_queryset() -> QuerySet[CarModification]:
    return (
        CarModification.objects.select_related("make", "model")
        .order_by("make__name", "model__name", "year", "modification", "engine")
    )


def get_autocatalog_garage_makes_queryset(*, year: int | None = None) -> QuerySet[CarMake]:
    queryset = CarMake.objects.filter(modifications__year__isnull=False)
    if year is not None:
        queryset = queryset.filter(modifications__year=year)
    return queryset.distinct().order_by("name")


def get_autocatalog_garage_models_queryset(*, make_id: str, year: int | None = None) -> QuerySet[CarModel]:
    if not make_id:
        return CarModel.objects.none()

    queryset = CarModel.objects.filter(make_id=make_id, modifications__year__isnull=False)
    if year is not None:
        queryset = queryset.filter(modifications__year=year)

    return (
        queryset
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
    queryset = CarModification.objects.all()
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

    years = (
        queryset
        .exclude(year__isnull=True)
        .values_list("year", flat=True)
        .distinct()
        .order_by("-year")
    )
    return [year for year in years if isinstance(year, int)]


def get_autocatalog_garage_modification_names(*, make_id: str, model_id: str, year: int | None) -> list[str]:
    if not make_id or not model_id:
        return []

    queryset = CarModification.objects.filter(make_id=make_id, model_id=model_id)
    if year is not None:
        queryset = queryset.filter(year=year)

    names = queryset.exclude(modification="").values_list("modification", flat=True).distinct().order_by("modification")
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

    queryset = CarModification.objects.filter(
        make_id=make_id,
        model_id=model_id,
        modification=modification.strip(),
        capacity=capacity.strip(),
    )
    if year is not None:
        queryset = queryset.filter(year=year)

    return queryset.exclude(engine="").select_related("make", "model").order_by("-year", "engine", "hp_from", "kw_from", "id")


def get_autocatalog_garage_capacities(
    *,
    make_id: str,
    model_id: str,
    year: int | None,
    modification: str,
) -> list[str]:
    if not make_id or not model_id or not modification:
        return []

    queryset = CarModification.objects.filter(
        make_id=make_id,
        model_id=model_id,
        modification=modification.strip(),
    )
    if year is not None:
        queryset = queryset.filter(year=year)

    capacities = queryset.exclude(capacity="").values_list("capacity", flat=True).distinct().order_by("capacity")
    return [value.strip() for value in capacities if isinstance(value, str) and value.strip()]
