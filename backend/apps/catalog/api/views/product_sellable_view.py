from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.pricing.services import ProductSellableSnapshotService


class ProductSellableSnapshotAPIView(APIView):
    def get(self, request, slug):
        product = get_object_or_404(
            Product.objects.filter(is_active=True)
            .select_related("product_price")
            .prefetch_related("supplier_offers", "supplier_offers__supplier"),
            slug=slug,
        )
        snapshot = ProductSellableSnapshotService().build(product=product, quantity=1)
        payload = {
            "product_id": str(product.id),
            **snapshot.to_public_payload(),
            "supplier_confidence": snapshot.supplier_confidence,
            "quality_hints": snapshot.quality_hints,
        }
        return Response(payload)
