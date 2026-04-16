from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import SupplierOfferOperationalSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors.pricing_selectors import apply_operational_supplier_offer_filters, get_operational_supplier_offers_queryset


class SupplierOfferOperationalListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = SupplierOfferOperationalSerializer
    ordering = ("-updated_at",)

    def get_queryset(self):
        queryset = get_operational_supplier_offers_queryset()
        queryset = apply_operational_supplier_offer_filters(queryset, params=self.request.query_params)

        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(supplier__name__icontains=query)
                | Q(supplier__code__icontains=query)
                | Q(supplier_sku__icontains=query)
                | Q(product__name__icontains=query)
                | Q(product__sku__icontains=query)
                | Q(product__article__icontains=query)
            )

        return queryset
