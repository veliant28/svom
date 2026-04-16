from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import ProductPriceOperationalSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors.pricing_selectors import apply_operational_product_price_filters, get_operational_product_prices_queryset


class ProductPriceOperationalListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ProductPriceOperationalSerializer
    ordering = ("-updated_at",)

    def get_queryset(self):
        queryset = get_operational_product_prices_queryset()
        queryset = apply_operational_product_price_filters(queryset, params=self.request.query_params)

        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(product__name__icontains=query)
                | Q(product__sku__icontains=query)
                | Q(product__article__icontains=query)
                | Q(product__brand__name__icontains=query)
                | Q(policy__name__icontains=query)
            )

        return queryset
