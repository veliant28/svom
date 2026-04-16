from __future__ import annotations

from apps.users.models import GarageVehicle


def ensure_primary_garage_vehicle(*, garage_vehicle: GarageVehicle) -> None:
    other_vehicles = GarageVehicle.objects.filter(user=garage_vehicle.user).exclude(pk=garage_vehicle.pk)
    should_be_primary = garage_vehicle.is_primary or not other_vehicles.exists()

    if should_be_primary:
        other_vehicles.filter(is_primary=True).update(is_primary=False)
        if not garage_vehicle.is_primary:
            garage_vehicle.is_primary = True
            garage_vehicle.save(update_fields=("is_primary", "updated_at"))
        return

    if GarageVehicle.objects.filter(user=garage_vehicle.user, is_primary=True).exists():
        return

    fallback_primary = other_vehicles.order_by("-created_at", "id").first()
    if fallback_primary is None:
        garage_vehicle.is_primary = True
        garage_vehicle.save(update_fields=("is_primary", "updated_at"))
        return

    fallback_primary.is_primary = True
    fallback_primary.save(update_fields=("is_primary", "updated_at"))


def reassign_primary_after_delete(*, user_id) -> None:
    remaining = GarageVehicle.objects.filter(user_id=user_id).order_by("-created_at", "id")
    if not remaining.exists() or remaining.filter(is_primary=True).exists():
        return

    next_primary = remaining.first()
    if next_primary is None:
        return

    next_primary.is_primary = True
    next_primary.save(update_fields=("is_primary", "updated_at"))
