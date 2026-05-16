from __future__ import annotations

from uuid import UUID

from django.db.models import BooleanField, Case, Exists, OuterRef, Q, QuerySet, Value, When

from apps.catalog.models import AutoDbProductLinkQuality, Category
from apps.catalog.services.category_vehicle_filter_policy import (
    SHOW_ALL_WITH_BADGES,
    VehicleFilterPolicy,
    get_vehicle_filter_policy,
    is_vehicle_filter_exempt_category,
)
from apps.compatibility.models import ProductFitment
from apps.users.models import GarageVehicle

FITMENT_ONLY = "only"
FITMENT_ALL = "all"
FITMENT_UNKNOWN = "unknown"
FITMENT_WITH_DATA = "with_data"


def is_fitment_disabled_category(category: Category | None) -> bool:
    return is_vehicle_filter_exempt_category(category)


class FitmentFilteringService:
    def apply(self, *, queryset: QuerySet, params) -> tuple[QuerySet, str | None]:
        selected_passanger_car_id, has_selected_vehicle = self._resolve_selected_passanger_car(params)
        vehicle_filter_policy = self._get_vehicle_filter_policy(params=params)
        fitment_mode = (params.get("fitment") or "").strip().lower()
        queryset = self._annotate_autodb_compatibility(
            queryset=queryset,
            selected_passanger_car_id=selected_passanger_car_id,
            has_selected_vehicle=has_selected_vehicle,
        )
        queryset = self._apply_fitment_mode(
            queryset=queryset,
            fitment_mode=fitment_mode,
            has_selected_vehicle=has_selected_vehicle,
            vehicle_filter_policy=vehicle_filter_policy,
        )
        return queryset, None

    # Catalog runtime policy: vehicle compatibility is Auto_DB-only.
    # Legacy UTR/modification/detail-id vehicle mapping is intentionally disabled.
    def _resolve_selected_passanger_car(self, params) -> tuple[int | None, bool]:
        vehicle_param_present = False
        for key in ("passanger_car_id", "vehicle_id"):
            raw_value = params.get(key)
            if raw_value not in (None, ""):
                vehicle_param_present = True
            parsed = self._parse_int(raw_value)
            if parsed:
                return parsed, True

        garage_vehicle_id = self._parse_uuid(params.get("garage_vehicle"))
        if garage_vehicle_id:
            vehicle_param_present = True
            row = (
                GarageVehicle.objects.filter(id=garage_vehicle_id)
                .values("catalog_source", "autodb_passanger_car_id")
                .first()
            )
            if row and str(row.get("catalog_source") or "").strip() == GarageVehicle.CATALOG_SOURCE_AUTODB_PRO:
                passanger_car_id = self._parse_int(row.get("autodb_passanger_car_id"))
                if passanger_car_id:
                    return passanger_car_id, True

        if params.get("car_modification") not in (None, ""):
            vehicle_param_present = True

        return None, vehicle_param_present

    def _annotate_autodb_compatibility(
        self,
        *,
        queryset: QuerySet,
        selected_passanger_car_id: int | None,
        has_selected_vehicle: bool,
    ) -> QuerySet:
        trusted_link_subquery = AutoDbProductLinkQuality.objects.filter(
            product_id=OuterRef("pk"),
            autodb_article_key=OuterRef("autodb_article_key"),
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        )
        fitments_any_subquery = ProductFitment.objects.filter(
            product_id=OuterRef("pk"),
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id__isnull=False,
            is_stale=False,
            excluded_from_public_filtering=False,
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
        )
        passenger_fitments_subquery = fitments_any_subquery.filter(linkage_type__iexact="PassengerCar")
        queryset = queryset.annotate(
            _has_trusted_link_quality=Exists(trusted_link_subquery),
            _has_fitment_relations=Exists(fitments_any_subquery),
        )
        queryset = queryset.annotate(
            has_fitment_data=Case(
                When(Q(_has_trusted_link_quality=True) & Q(_has_fitment_relations=True), then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            )
        )
        if selected_passanger_car_id:
            selected_fitments = passenger_fitments_subquery.filter(autodb_passanger_car_id=selected_passanger_car_id)
            queryset = queryset.annotate(_fits_selected_vehicle_rel=Exists(selected_fitments))
            return queryset.annotate(
                fits_selected_vehicle=Case(
                    When(Q(_has_trusted_link_quality=True) & Q(_fits_selected_vehicle_rel=True), then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                )
            )
        if has_selected_vehicle:
            return queryset.annotate(fits_selected_vehicle=Value(False, output_field=BooleanField()))
        return queryset.annotate(fits_selected_vehicle=Value(None, output_field=BooleanField(null=True)))

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

    def _apply_fitment_mode(
        self,
        *,
        queryset: QuerySet,
        fitment_mode: str,
        has_selected_vehicle: bool,
        vehicle_filter_policy: VehicleFilterPolicy,
    ) -> QuerySet:
        effective_mode = fitment_mode or (FITMENT_ONLY if has_selected_vehicle else FITMENT_ALL)
        if vehicle_filter_policy == SHOW_ALL_WITH_BADGES and effective_mode == FITMENT_ONLY:
            effective_mode = FITMENT_ALL

        if effective_mode == FITMENT_UNKNOWN:
            return queryset.filter(has_fitment_data=False)

        if effective_mode == FITMENT_WITH_DATA:
            return queryset.filter(has_fitment_data=True)

        if effective_mode == FITMENT_ONLY and has_selected_vehicle:
            return queryset.filter(fits_selected_vehicle=True)

        return queryset

    def _get_vehicle_filter_policy(self, *, params) -> VehicleFilterPolicy:
        category = self._resolve_category_from_params(params)
        return get_vehicle_filter_policy(category)

    def _resolve_category_from_params(self, params) -> Category | None:
        category_id = self._parse_uuid(params.get("category_id"))
        if category_id:
            return (
                Category.objects.select_related("parent", "parent__parent", "parent__parent__parent")
                .filter(id=category_id)
                .first()
            )

        category_slug = str(params.get("category") or "").strip()
        if category_slug:
            return (
                Category.objects.select_related("parent", "parent__parent", "parent__parent__parent")
                .filter(slug=category_slug)
                .first()
            )

        return None
