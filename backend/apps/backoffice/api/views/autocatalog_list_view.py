from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.backoffice.api.pagination import SupplierRawOfferPagination
from apps.backoffice.api.serializers import BackofficeAutocatalogCarSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors import (
    apply_autocatalog_filters,
    get_autocatalog_filter_options,
    get_autocatalog_modifications_queryset,
)


class BackofficeAutocatalogListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeAutocatalogCarSerializer
    pagination_class = SupplierRawOfferPagination
    ordering = ("make__name", "model__name", "year", "modification")

    def get_queryset(self):
        queryset = get_autocatalog_modifications_queryset()
        return apply_autocatalog_filters(queryset=queryset, params=self.request.query_params)


class BackofficeAutocatalogFilterOptionsAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]

    def get(self, request):
        queryset = get_autocatalog_modifications_queryset()
        options = get_autocatalog_filter_options(queryset=queryset, params=request.query_params)
        return Response(options)
