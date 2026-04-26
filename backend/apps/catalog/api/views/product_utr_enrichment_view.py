from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.services.utr_product_enrichment import request_visible_utr_enrichment


class ProductUtrEnrichmentAPIView(APIView):
    def post(self, request):
        product_ids = request.data.get("product_ids", []) if isinstance(request.data, dict) else []
        if not isinstance(product_ids, list):
            return Response({"detail": "product_ids must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        enqueue = True
        if isinstance(request.data, dict) and "enqueue" in request.data:
            enqueue = bool(request.data.get("enqueue"))

        rows = request_visible_utr_enrichment(product_ids=product_ids, request=request, enqueue=enqueue)
        return Response({"results": rows})
