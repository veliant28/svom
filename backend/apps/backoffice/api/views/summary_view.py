from rest_framework.response import Response

from apps.backoffice.api.serializers import BackofficeSummarySerializer
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.selectors import build_backoffice_summary_payload


class BackofficeSummaryAPIView(BackofficeAPIView):
    def get(self, request):
        payload = build_backoffice_summary_payload()
        serializer = BackofficeSummarySerializer(payload)
        return Response(serializer.data)
