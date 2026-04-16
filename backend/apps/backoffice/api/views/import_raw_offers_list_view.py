from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.pagination import SupplierRawOfferPagination
from apps.backoffice.api.serializers import SupplierRawOfferSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors.imports_selectors import apply_import_raw_offer_filters, get_import_raw_offers_queryset


class SupplierRawOfferListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = SupplierRawOfferSerializer
    pagination_class = SupplierRawOfferPagination
    ordering = ("-created_at",)

    def get_queryset(self):
        queryset = get_import_raw_offers_queryset()
        queryset = apply_import_raw_offer_filters(queryset, params=self.request.query_params)

        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(external_sku__icontains=query)
                | Q(article__icontains=query)
                | Q(brand_name__icontains=query)
                | Q(product_name__icontains=query)
                | Q(supplier__code__icontains=query)
            )

        return queryset
