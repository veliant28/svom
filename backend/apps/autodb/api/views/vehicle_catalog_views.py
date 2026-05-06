from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.autodb.api.serializers import (
    AutoDbVehicleCatalogResponseSerializer,
    AutoDbVehicleFilterOptionsSerializer,
    AutoDbPassangerCarAttributeSerializer,
    AutoDbPassangerCarSerializer,
    AutoDbVehicleManufacturerSerializer,
    AutoDbVehicleModelSerializer,
    AutoDbVehicleSearchResponseSerializer,
)
from apps.autodb.selectors.admin_vehicle_catalog import (
    list_admin_vehicle_catalog,
    list_admin_vehicle_filter_options,
)
from apps.autodb.selectors import (
    get_passanger_car,
    list_passanger_car_attributes,
    list_passanger_cars,
    list_vehicle_manufacturers,
    list_vehicle_models,
    search_passanger_cars,
    search_vehicle_manufacturers,
    search_vehicle_models,
)


class AutoDbVehicleCatalogFlagMixin:
    disabled_message = "Auto_DB_Pro vehicle catalog API is disabled by configuration."

    def _is_enabled(self) -> bool:
        return bool(getattr(settings, "AUTODB_PRO_VEHICLE_CATALOG_API_ENABLED", False))

    def _disabled_response(self) -> Response:
        return Response({"detail": self.disabled_message}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


def _parse_positive_int(value: str | None) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _parse_bool(value: str | None) -> bool:
    raw = str(value or "").strip().lower()
    return raw in {"1", "true", "t", "yes", "y", "on"}


class AutoDbVehicleManufacturersAPIView(AutoDbVehicleCatalogFlagMixin, APIView):
    def get(self, request):
        if not self._is_enabled():
            return self._disabled_response()

        payload = list_vehicle_manufacturers()
        serializer = AutoDbVehicleManufacturerSerializer(payload, many=True)
        return Response(serializer.data)


class AutoDbVehicleManufacturerModelsAPIView(AutoDbVehicleCatalogFlagMixin, APIView):
    def get(self, request, manufacturer_id: int):
        if not self._is_enabled():
            return self._disabled_response()

        payload = list_vehicle_models(manufacturer_id=manufacturer_id)
        serializer = AutoDbVehicleModelSerializer(payload, many=True)
        return Response(serializer.data)


class AutoDbVehicleModelPassangerCarsAPIView(AutoDbVehicleCatalogFlagMixin, APIView):
    def get(self, request, model_id: int):
        if not self._is_enabled():
            return self._disabled_response()

        payload = list_passanger_cars(model_id=model_id)
        serializer = AutoDbPassangerCarSerializer(payload, many=True)
        return Response(serializer.data)


class AutoDbPassangerCarDetailAPIView(AutoDbVehicleCatalogFlagMixin, APIView):
    def get(self, request, id: int):
        if not self._is_enabled():
            return self._disabled_response()

        payload = get_passanger_car(passanger_car_id=id)
        if payload is None:
            return Response({"detail": "Passanger car not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AutoDbPassangerCarSerializer(payload)
        return Response(serializer.data)


class AutoDbPassangerCarAttributesAPIView(AutoDbVehicleCatalogFlagMixin, APIView):
    def get(self, request, id: int):
        if not self._is_enabled():
            return self._disabled_response()

        payload = list_passanger_car_attributes(passanger_car_id=id)
        serializer = AutoDbPassangerCarAttributeSerializer(payload, many=True)
        return Response(serializer.data)


class AutoDbVehicleSearchAPIView(AutoDbVehicleCatalogFlagMixin, APIView):
    def get(self, request):
        if not self._is_enabled():
            return self._disabled_response()

        query = str(request.query_params.get("q", "") or "").strip()
        manufacturer_id = str(request.query_params.get("manufacturer_id", "") or "").strip()
        model_id = str(request.query_params.get("model_id", "") or "").strip()

        payload = {
            "manufacturers": search_vehicle_manufacturers(query=query) if query else [],
            "models": search_vehicle_models(manufacturer_id=manufacturer_id, query=query) if query and manufacturer_id else [],
            "passanger_cars": search_passanger_cars(model_id=model_id, query=query) if query and model_id else [],
        }
        serializer = AutoDbVehicleSearchResponseSerializer(payload)
        return Response(serializer.data)


class AutoDbVehicleFilterOptionsAPIView(AutoDbVehicleCatalogFlagMixin, APIView):
    def get(self, request):
        if not self._is_enabled():
            return self._disabled_response()

        payload = list_admin_vehicle_filter_options(
            year=_parse_positive_int(request.query_params.get("year")),
            manufacturer_id=_parse_positive_int(request.query_params.get("manufacturer_id")),
            model_id=_parse_positive_int(request.query_params.get("model_id")),
            modification=str(request.query_params.get("modification") or "").strip(),
            volume=str(request.query_params.get("volume") or "").strip(),
            years_only=_parse_bool(request.query_params.get("years_only")),
        )
        serializer = AutoDbVehicleFilterOptionsSerializer(payload)
        return Response(serializer.data)


class AutoDbVehicleCatalogAPIView(AutoDbVehicleCatalogFlagMixin, APIView):
    def get(self, request):
        if not self._is_enabled():
            return self._disabled_response()

        payload = list_admin_vehicle_catalog(
            manufacturer_id=_parse_positive_int(request.query_params.get("manufacturer_id")),
            model_id=_parse_positive_int(request.query_params.get("model_id")),
            year=_parse_positive_int(request.query_params.get("year")),
            q=str(request.query_params.get("q") or "").strip(),
            modification=str(request.query_params.get("modification") or "").strip(),
            volume=str(request.query_params.get("volume") or "").strip(),
            engine=str(request.query_params.get("engine") or "").strip(),
            page=_parse_positive_int(request.query_params.get("page")) or 1,
            page_size=_parse_positive_int(request.query_params.get("page_size")) or 50,
        )
        serializer = AutoDbVehicleCatalogResponseSerializer(payload)
        return Response(serializer.data)
