from __future__ import annotations

from django.utils.text import slugify

from apps.vehicles.models import VehicleMake, VehicleModel


def normalize_vehicle_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def _unique_slug(*, base: str, exists_fn) -> str:
    normalized = slugify(base) or "item"
    candidate = normalized
    index = 2
    while exists_fn(candidate):
        candidate = f"{normalized}-{index}"
        index += 1
    return candidate


def generate_unique_make_slug(
    *,
    name: str,
    preferred_slug: str | None = None,
    exclude_make_id: str | None = None,
) -> str:
    base = (preferred_slug or "").strip() or name
    queryset = VehicleMake.objects.all()
    if exclude_make_id:
        queryset = queryset.exclude(id=exclude_make_id)

    return _unique_slug(
        base=base,
        exists_fn=lambda candidate: queryset.filter(slug=candidate).exists(),
    )


def generate_unique_model_slug(
    *,
    make: VehicleMake,
    name: str,
    preferred_slug: str | None = None,
    exclude_model_id: str | None = None,
) -> str:
    base = (preferred_slug or "").strip() or name
    queryset = VehicleModel.objects.filter(make=make)
    if exclude_model_id:
        queryset = queryset.exclude(id=exclude_model_id)

    return _unique_slug(
        base=base,
        exists_fn=lambda candidate: queryset.filter(slug=candidate).exists(),
    )
