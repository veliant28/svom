from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import BackofficeOrderOperationalListSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors import apply_operational_order_filters, get_operational_orders_queryset


class OrderOperationalListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeOrderOperationalListSerializer

    def get_queryset(self):
        queryset = get_operational_orders_queryset()
        queryset = apply_operational_order_filters(queryset, params=self.request.query_params)

        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(order_number__icontains=query)
                | Q(contact_full_name__icontains=query)
                | Q(contact_phone__icontains=query)
                | Q(contact_email__icontains=query)
            ).distinct()

        return queryset
