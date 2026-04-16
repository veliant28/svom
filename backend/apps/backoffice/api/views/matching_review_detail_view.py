from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import SupplierRawOfferSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors import get_import_raw_offers_queryset


class MatchingReviewDetailAPIView(RetrieveAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = SupplierRawOfferSerializer
    lookup_field = "id"

    def get_queryset(self):
        return get_import_raw_offers_queryset()
