from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _

from apps.backoffice.api.serializers import ProcurementItemRecommendationSerializer, ProcurementSuggestionsSerializer
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.selectors import apply_operational_order_filters, get_operational_orders_queryset
from apps.backoffice.services import ProcurementService
from apps.commerce.models import Order


class ProcurementSuggestionsListAPIView(BackofficeAPIView):
    DEFAULT_STATUSES = {
        Order.STATUS_NEW,
        Order.STATUS_PROCESSING,
    }

    def get(self, request):
        queryset = get_operational_orders_queryset()
        queryset = apply_operational_order_filters(queryset, params=request.query_params)

        status_query = request.query_params.get("statuses", "").strip()
        if status_query:
            statuses = {value.strip() for value in status_query.split(",") if value.strip()}
            queryset = queryset.filter(status__in=statuses)
        else:
            queryset = queryset.filter(status__in=self.DEFAULT_STATUSES)

        limit_raw = request.query_params.get("limit", "50").strip()
        try:
            limit = max(min(int(limit_raw), 500), 1)
        except ValueError:
            limit = 50

        orders = list(queryset[:limit])
        payload = ProcurementService().build_grouped_suggestions(orders)
        serializer = ProcurementSuggestionsSerializer(payload)
        return Response(serializer.data)


class ProcurementItemRecommendationAPIView(BackofficeAPIView):
    def get(self, request, item_id):
        queryset = (
            Order.objects.prefetch_related("items")
            .filter(items__id=item_id)
            .distinct()
        )
        order = queryset.first()
        if order is None:
            return Response({"detail": _("Order item not found.")}, status=404)

        item = order.items.get(id=item_id)
        payload = ProcurementService().build_item_recommendation(item)
        serializer = ProcurementItemRecommendationSerializer(payload)
        return Response(serializer.data)
