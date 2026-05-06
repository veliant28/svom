from __future__ import annotations

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.autodb.selectors.admin_vehicle_catalog import (
    list_admin_vehicle_catalog,
    list_admin_vehicle_filter_options,
    list_admin_vehicle_manufacturers,
    list_admin_vehicle_models,
)
from apps.backoffice.api.serializers import (
    BackofficeAutoDbVehicleCatalogRowSerializer,
    BackofficeAutoDbVehicleManufacturerSerializer,
    BackofficeAutoDbVehicleModelSerializer,
)
from apps.backoffice.permissions import IsStaffOrSuperuser


def _parse_positive_int(value: str | None) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


class BackofficeAutoDbVehicleCatalogAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]

    def get(self, request):
        payload = list_admin_vehicle_catalog(
            manufacturer_id=_parse_positive_int(request.query_params.get("manufacturer_id")),
            model_id=_parse_positive_int(request.query_params.get("model_id")),
            year=_parse_positive_int(request.query_params.get("year")),
            q=str(request.query_params.get("q") or "").strip(),
            modification=str(request.query_params.get("modification") or "").strip(),
            volume=str(request.query_params.get("volume") or "").strip(),
            engine=str(request.query_params.get("engine") or "").strip(),
            page=_parse_positive_int(request.query_params.get("page")) or 1,
            page_size=_parse_positive_int(request.query_params.get("page_size")) or 25,
        )
        serializer = BackofficeAutoDbVehicleCatalogRowSerializer(payload.get("results", []), many=True)
        return Response(
            {
                "count": int(payload.get("count") or 0),
                "results": serializer.data,
            }
        )


class BackofficeAutoDbVehicleManufacturersAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]

    def get(self, request):
        rows = list_admin_vehicle_manufacturers(q=str(request.query_params.get("q") or "").strip())
        serializer = BackofficeAutoDbVehicleManufacturerSerializer(rows, many=True)
        return Response(serializer.data)


class BackofficeAutoDbVehicleFilterOptionsAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]

    def get(self, request):
        payload = list_admin_vehicle_filter_options(
            year=_parse_positive_int(request.query_params.get("year")),
            manufacturer_id=_parse_positive_int(request.query_params.get("manufacturer_id")),
            model_id=_parse_positive_int(request.query_params.get("model_id")),
            modification=str(request.query_params.get("modification") or "").strip(),
            volume=str(request.query_params.get("volume") or "").strip(),
        )
        return Response(payload)


class BackofficeAutoDbVehicleModelsAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]

    def get(self, request, manufacturer_id: int):
        rows = list_admin_vehicle_models(
            manufacturer_id=manufacturer_id,
            q=str(request.query_params.get("q") or "").strip(),
        )
        serializer = BackofficeAutoDbVehicleModelSerializer(rows, many=True)
        return Response(serializer.data)
