from __future__ import annotations

import re
from uuid import UUID

from django.db.models import BooleanField, Case, Exists, OuterRef, Q, QuerySet, Value, When

from apps.autocatalog.models import UtrArticleDetailMap, UtrDetailCarMap
from apps.catalog.models import Category
from apps.compatibility.models import ProductFitment
from apps.supplier_imports.models import SupplierRawOffer
from apps.users.models import GarageVehicle

FITMENT_ONLY = "only"
FITMENT_ALL = "all"
FITMENT_UNKNOWN = "unknown"
FITMENT_WITH_DATA = "with_data"
FITMENT_DISABLED_CATEGORY_SIGNATURES = {
    "автохіміятааксесуари",
    "автохимияиаксессуары",
    "autochemicalsandaccessories",
    "шинитадиски",
    "шиныидиски",
    "tiresandwheels",
}

def normalize_category_signature(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    return re.sub(r"[^0-9a-zа-яіїєґ]+", "", raw, flags=re.IGNORECASE)


def is_fitment_disabled_category(category: Category | None) -> bool:
    current = category
    visited: set[str] = set()
    while current is not None:
        category_id = str(current.id)
        if category_id in visited:
            break
        visited.add(category_id)

        candidates = (
            current.slug,
            current.name,
            getattr(current, "name_uk", ""),
            getattr(current, "name_ru", ""),
            getattr(current, "name_en", ""),
        )
        for candidate in candidates:
            signature = normalize_category_signature(candidate)
            if signature and signature in FITMENT_DISABLED_CATEGORY_SIGNATURES:
                return True
        current = current.parent

    return False


class FitmentFilteringService:
    def apply(self, *, queryset: QuerySet, params) -> tuple[QuerySet, str | None]:
        selected_modification_id, selected_utr_detail_ids = self._resolve_selection(params)
        vehicle_fitment_disabled = self._is_vehicle_fitment_disabled(params=params)
        queryset = self._annotate_compatibility(
            queryset=queryset,
            selected_modification_id=selected_modification_id,
            selected_utr_detail_ids=selected_utr_detail_ids,
        )
        queryset = self._apply_fitment_mode(
            queryset=queryset,
            fitment_mode=(params.get("fitment") or "").strip().lower(),
            has_selected_vehicle=bool(selected_modification_id or selected_utr_detail_ids),
            vehicle_fitment_disabled=vehicle_fitment_disabled,
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
        utr_any_map_subquery = self._build_utr_raw_offer_any_map_subquery()
        queryset = queryset.annotate(
            _has_fitment_relations=Exists(fitments_subquery),
            _has_utr_article_map=Exists(utr_any_map_subquery),
        ).annotate(
            has_fitment_data=Case(
                When(
                    Q(_has_fitment_relations=True) | Q(_has_utr_article_map=True) | Q(utr_detail_id__gt=""),
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            )
        )

        if selected_modification_id:
            selected_fitments_subquery = fitments_subquery.filter(modification_id=selected_modification_id)
            return queryset.annotate(fits_selected_vehicle=Exists(selected_fitments_subquery))

        if selected_utr_detail_ids:
            utr_vehicle_match_subquery = self._build_utr_raw_offer_vehicle_match_subquery(
                selected_utr_detail_ids=selected_utr_detail_ids
            )
            return queryset.annotate(
                _utr_article_matches_vehicle=Exists(utr_vehicle_match_subquery),
                fits_selected_vehicle=Case(
                    When(Q(utr_detail_id__in=selected_utr_detail_ids) | Q(_utr_article_matches_vehicle=True), then=Value(True)),
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
        vehicle_fitment_disabled: bool = False,
    ) -> QuerySet:
        effective_mode = fitment_mode or (FITMENT_ONLY if has_selected_vehicle else FITMENT_ALL)
        if vehicle_fitment_disabled and effective_mode == FITMENT_ONLY:
            effective_mode = FITMENT_ALL

        if effective_mode == FITMENT_UNKNOWN:
            return queryset.filter(has_fitment_data=False)

        if effective_mode == FITMENT_WITH_DATA:
            return queryset.filter(has_fitment_data=True)

        if effective_mode == FITMENT_ONLY and has_selected_vehicle:
            return queryset.filter(fits_selected_vehicle=True)

        return queryset

    def _is_vehicle_fitment_disabled(self, *, params) -> bool:
        category = self._resolve_category_from_params(params)
        return is_fitment_disabled_category(category)

    def _resolve_category_from_params(self, params) -> Category | None:
        category_id = self._parse_uuid(params.get("category_id"))
        if category_id:
            return Category.objects.select_related("parent").filter(id=category_id).first()

        category_slug = str(params.get("category") or "").strip()
        if category_slug:
            return Category.objects.select_related("parent").filter(slug=category_slug).first()

        return None

    def _build_utr_raw_offer_any_map_subquery(self):
        return SupplierRawOffer.objects.filter(
            matched_product_id=OuterRef("pk"),
            supplier__code="utr",
        ).filter(
            Exists(
                UtrArticleDetailMap.objects.filter(
                    normalized_article=OuterRef("normalized_article"),
                    normalized_brand=OuterRef("normalized_brand"),
                )
            )
        )

    def _build_utr_raw_offer_vehicle_match_subquery(self, *, selected_utr_detail_ids: list[str]):
        return SupplierRawOffer.objects.filter(
            matched_product_id=OuterRef("pk"),
            supplier__code="utr",
        ).filter(
            Exists(
                UtrArticleDetailMap.objects.filter(
                    utr_detail_id__in=selected_utr_detail_ids,
                    normalized_article=OuterRef("normalized_article"),
                    normalized_brand=OuterRef("normalized_brand"),
                )
            )
        )
