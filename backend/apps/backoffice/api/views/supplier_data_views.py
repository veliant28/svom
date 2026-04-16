from django.core.exceptions import ObjectDoesNotExist
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.backoffice.api.serializers import ImportRowErrorSerializer, ImportRunSerializer, SupplierOfferOperationalSerializer
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors import (
    apply_supplier_prices_filters,
    get_supplier_errors_queryset,
    get_supplier_prices_queryset,
    get_supplier_runs_queryset,
)
from apps.backoffice.services import SupplierWorkspaceService


class SupplierPricesListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = SupplierOfferOperationalSerializer

    def get_queryset(self):
        supplier_code = self.kwargs["code"]
        queryset = get_supplier_prices_queryset(supplier_code=supplier_code)
        query = self.request.query_params.get("q", "").strip()
        availability = self.request.query_params.get("is_available", "").strip().lower()
        queryset = apply_supplier_prices_filters(queryset=queryset, query=query, availability=availability)
        return queryset


class SupplierRunsListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ImportRunSerializer

    def get_queryset(self):
        supplier_code = self.kwargs["code"]
        return get_supplier_runs_queryset(supplier_code=supplier_code)


class SupplierErrorsListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ImportRowErrorSerializer

    def get_queryset(self):
        supplier_code = self.kwargs["code"]
        run_id = self.request.query_params.get("run_id", "").strip()
        latest_only = self.request.query_params.get("latest_only", "true").strip().lower() not in {"0", "false", "no"}
        return get_supplier_errors_queryset(
            supplier_code=supplier_code,
            run_id=run_id,
            latest_only=latest_only,
        )


class SupplierCooldownAPIView(BackofficeAPIView):
    def get(self, request, code: str):
        try:
            payload = SupplierWorkspaceService().get_cooldown(supplier_code=code)
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=404)
        return Response(payload, status=200)
