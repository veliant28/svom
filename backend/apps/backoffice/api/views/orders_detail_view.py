from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import BackofficeOrderOperationalDetailSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors import get_operational_orders_queryset


class OrderOperationalDetailAPIView(RetrieveAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeOrderOperationalDetailSerializer
    lookup_field = "id"

    def get_queryset(self):
        return get_operational_orders_queryset()
