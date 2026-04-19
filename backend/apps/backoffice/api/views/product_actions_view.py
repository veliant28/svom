from rest_framework import serializers, status
from rest_framework.response import Response

from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.services import ProductOperationsService
from apps.catalog.models import Category


class ProductBulkMoveCategoryActionSerializer(serializers.Serializer):
    product_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    category_id = serializers.UUIDField()
    update_import_rules = serializers.BooleanField(required=False, default=True)


class BulkMoveProductsCategoryActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = ProductBulkMoveCategoryActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        category_id = serializer.validated_data["category_id"]
        category = Category.objects.filter(id=category_id, is_active=True).first()
        if category is None:
            return Response({"detail": "Category not found."}, status=status.HTTP_404_NOT_FOUND)

        product_ids = [str(value) for value in serializer.validated_data["product_ids"]]
        update_import_rules = serializer.validated_data["update_import_rules"]

        result = ProductOperationsService().bulk_move_to_category(
            product_ids=product_ids,
            category=category,
            actor=request.user,
            update_import_rules=update_import_rules,
        )

        return Response(
            {
                "target_category_id": str(category.id),
                "products_requested": result.requested,
                "products_found": result.found,
                "products_updated": result.products_updated,
                "raw_offers_total": result.raw_offers_total,
                "raw_offers_updated": result.raw_offers_updated,
                "update_import_rules": result.update_import_rules,
            },
            status=status.HTTP_200_OK,
        )
