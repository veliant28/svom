from __future__ import annotations

from uuid import UUID

from django.db.models import BooleanField, Case, Exists, OuterRef, QuerySet, Value, When

from apps.autocatalog.models import UtrDetailCarMap
from apps.compatibility.models import ProductFitment
from apps.users.models import GarageVehicle

FITMENT_ONLY = "only"
FITMENT_ALL = "all"
FITMENT_UNKNOWN = "unknown"
FITMENT_WITH_DATA = "with_data"


class FitmentFilteringService:
    def apply(self, *, queryset: QuerySet, params) -> tuple[QuerySet, str | None]:
        selected_modification_id, selected_utr_detail_ids = self._resolve_selection(params)
        queryset = self._annotate_compatibility(
            queryset=queryset,
            selected_modification_id=selected_modification_id,
            selected_utr_detail_ids=selected_utr_detail_ids,
        )
        queryset = self._apply_fitment_mode(
            queryset=queryset,
            fitment_mode=(params.get("fitment") or "").strip().lower(),
            has_selected_vehicle=bool(selected_modification_id or selected_utr_detail_ids),
        )
        return queryset, selected_modification_id

    def _resolve_selection(self, params) -> tuple[str | None, list[str]]:
        explicit_modification = self._parse_uuid(params.get("modification"))
        if explicit_modification:
            return explicit_modification, []

        explicit_car_modification_id = self._parse_int(params.get("car_modification"))
        if explicit_car_modification_id:
            return None, self._resolve_utr_detail_ids(explicit_car_modification_id)

        garage_vehicle_id = self._parse_uuid(params.get("garage_vehicle"))
        if not garage_vehicle_id:
            return None, []

        garage_vehicle = (
            GarageVehicle.objects.filter(id=garage_vehicle_id)
            .values("modification_id", "car_modification_id")
            .first()
        )
        if not garage_vehicle:
            return None, []

        selected_modification_id = self._parse_uuid(garage_vehicle.get("modification_id"))
        if selected_modification_id:
            return selected_modification_id, []

        selected_car_modification_id = self._parse_int(garage_vehicle.get("car_modification_id"))
        if not selected_car_modification_id:
            return None, []

        return None, self._resolve_utr_detail_ids(selected_car_modification_id)

    def _resolve_utr_detail_ids(self, car_modification_id: int) -> list[str]:
        selected_utr_detail_ids = list(
            UtrDetailCarMap.objects.filter(car_modification_id=car_modification_id)
            .values_list("utr_detail_id", flat=True)
            .distinct()
            .order_by("utr_detail_id")
        )
        return [detail_id for detail_id in selected_utr_detail_ids if detail_id]

    def _parse_uuid(self, value) -> str | None:
        if not value:
            return None
        try:
            return str(UUID(str(value).strip()))
        except (TypeError, ValueError, AttributeError):
            return None

    def _parse_int(self, value) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _annotate_compatibility(
        self,
        *,
        queryset: QuerySet,
        selected_modification_id: str | None,
        selected_utr_detail_ids: list[str],
    ) -> QuerySet:
        fitments_subquery = ProductFitment.objects.filter(product_id=OuterRef("pk"))
        queryset = queryset.annotate(has_fitment_data=Exists(fitments_subquery))

        if selected_modification_id:
            selected_fitments_subquery = fitments_subquery.filter(modification_id=selected_modification_id)
            return queryset.annotate(fits_selected_vehicle=Exists(selected_fitments_subquery))

        if selected_utr_detail_ids:
            return queryset.annotate(
                fits_selected_vehicle=Case(
                    When(utr_detail_id__in=selected_utr_detail_ids, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                )
            )

        return queryset.annotate(fits_selected_vehicle=Value(None, output_field=BooleanField(null=True)))

    def _apply_fitment_mode(
        self,
        *,
        queryset: QuerySet,
        fitment_mode: str,
        has_selected_vehicle: bool,
    ) -> QuerySet:
        effective_mode = fitment_mode or (FITMENT_ONLY if has_selected_vehicle else FITMENT_ALL)

        if effective_mode == FITMENT_UNKNOWN:
            return queryset.filter(has_fitment_data=False)

        if effective_mode == FITMENT_WITH_DATA:
            return queryset.filter(has_fitment_data=True)

        if effective_mode == FITMENT_ONLY and has_selected_vehicle:
            return queryset.filter(fits_selected_vehicle=True)

        return queryset
