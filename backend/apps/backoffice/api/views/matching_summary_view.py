from rest_framework.response import Response

from apps.backoffice.api.serializers import MatchingSummarySerializer
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.services import MatchingReviewService


class MatchingSummaryAPIView(BackofficeAPIView):
    def get(self, request):
        payload = MatchingReviewService().get_summary()
        serializer = MatchingSummarySerializer(payload)
        return Response(serializer.data)
