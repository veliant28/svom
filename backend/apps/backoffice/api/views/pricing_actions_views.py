from rest_framework import serializers
from rest_framework.response import Response

from apps.backoffice.api.views._base import BackofficeAPIView
from apps.search.tasks import reindex_products_task


class ProductIdsActionSerializer(serializers.Serializer):
    product_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    dispatch_async = serializers.BooleanField(required=False, default=True)


class ReindexProductsActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = ProductIdsActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_ids = [str(value) for value in serializer.validated_data["product_ids"]]
        dispatch_async = serializer.validated_data["dispatch_async"]

        if dispatch_async:
            reindex_products_task.delay(product_ids=product_ids)
            return Response({"mode": "async", "queued": len(product_ids)})

        summary = reindex_products_task(product_ids=product_ids)
        return Response({"mode": "sync", "queued": len(product_ids), "summary": summary})
