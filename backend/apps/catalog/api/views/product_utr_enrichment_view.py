from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class ProductUtrEnrichmentAPIView(APIView):
    def post(self, request):
        return Response(
            {
                "detail": "UTR catalog enrichment is disabled. UTR is price supplier only.",
                "results": [],
            },
            status=status.HTTP_410_GONE,
        )
