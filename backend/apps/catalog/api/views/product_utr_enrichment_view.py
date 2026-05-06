from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.catalog.services.autodb_content import get_autodb_product_content


class ProductUtrEnrichmentAPIView(APIView):
    def post(self, request):
        product_ids = request.data.get("product_ids", []) if isinstance(request.data, dict) else []
        if not isinstance(product_ids, list):
            return Response({"detail": "product_ids must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        prefer_live = True
        if isinstance(request.data, dict) and "prefer_live" in request.data:
            prefer_live = bool(request.data.get("prefer_live"))

        rows: list[dict[str, object]] = []
        queryset = Product.objects.filter(id__in=[str(value) for value in product_ids]).order_by("name")
        for product in queryset:
            content = get_autodb_product_content(product=product, prefer_live=prefer_live)
            rows.append(
                {
                    "product_id": str(product.id),
                    "status": "fetched",
                    "images_count": len(content.image_urls),
                    "attributes_count": len(content.attributes),
                    "category_candidates_count": len(content.product_groups),
                }
            )
        return Response({"results": rows})
