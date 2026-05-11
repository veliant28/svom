from django.db.models import Case, F, IntegerField, QuerySet, When
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.api.serializers import ProductListSerializer
from apps.catalog.selectors import get_public_products_queryset
from apps.catalog.services import FitmentFilteringService


class HomePopularProductsAPIView(APIView):
    serializer_class = ProductListSerializer
    limit = 20

    @staticmethod
    def _with_positive_supplier_stock(queryset):
        return queryset.filter(
            supplier_offers__is_available=True,
            supplier_offers__stock_qty__gt=0,
        ).distinct()

    @staticmethod
    def _order_by_ids(queryset: QuerySet, ordered_ids: list) -> QuerySet:
        whens = [When(id=product_id, then=index) for index, product_id in enumerate(ordered_ids)]
        return queryset.order_by(Case(*whens, output_field=IntegerField()))

    def _resolve_ordered_ids(self) -> list:
        queryset = get_public_products_queryset().annotate(
            available_stock_qty=F("available_stock_qty_cached"),
        )
        queryset, _ = FitmentFilteringService().apply(
            queryset=queryset,
            params=self.request.query_params,
        )
        eligible = self._with_positive_supplier_stock(queryset).filter(
            product_price__final_price__gt=0,
        )

        featured_ids = list(
            eligible
            .filter(is_featured=True)
            .order_by("-updated_at", "-created_at", "-available_stock_qty_cached", "name", "id")
            .values_list("id", flat=True)[: self.limit]
        )

        remaining_limit = self.limit - len(featured_ids)
        if remaining_limit <= 0:
            return featured_ids

        fallback_ids = list(
            eligible
            .exclude(id__in=featured_ids)
            .order_by("-views_count", "-updated_at", "-created_at", "-available_stock_qty_cached", "name", "id")
            .values_list("id", flat=True)[:remaining_limit]
        )
        return [*featured_ids, *fallback_ids]

    def get(self, request):
        ordered_ids = self._resolve_ordered_ids()
        if not ordered_ids:
            return Response([])

        queryset = self._order_by_ids(
            get_public_products_queryset().filter(id__in=ordered_ids),
            ordered_ids,
        )
        serializer = self.serializer_class(queryset, many=True, context={"request": request})
        return Response(serializer.data)

