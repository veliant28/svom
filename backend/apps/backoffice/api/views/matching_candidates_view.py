from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.response import Response

from apps.backoffice.api.serializers import MatchingCandidateProductSerializer
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.services import MatchingReviewService
from apps.supplier_imports.models import SupplierRawOffer


class MatchingCandidatesAPIView(BackofficeAPIView):
    def get(self, request, id: str):
        try:
            raw_offer = SupplierRawOffer.objects.select_related("supplier", "source", "matched_product").get(id=id)
        except ObjectDoesNotExist:
            return Response({"detail": "Raw offer not found."}, status=status.HTTP_404_NOT_FOUND)
        candidates = MatchingReviewService().get_candidates(raw_offer=raw_offer)
        serializer = MatchingCandidateProductSerializer(candidates, many=True)
        return Response(
            {
                "raw_offer_id": str(raw_offer.id),
                "count": len(candidates),
                "results": serializer.data,
            }
        )
