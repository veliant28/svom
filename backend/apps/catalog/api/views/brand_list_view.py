from django.db.models import QuerySet
from django.utils.text import slugify
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.api.serializers import BrandListSerializer
from apps.catalog.models import Product


class BrandListAPIView(APIView):
    serializer_class = BrandListSerializer

    def get(self, request):
        queryset: QuerySet = (
            Product.objects.filter(is_active=True)
            .exclude(display_brand_name__isnull=True)
            .exclude(display_brand_name="")
            .values("autodb_supplier_id", "display_brand_name")
            .distinct()
            .order_by("display_brand_name")
        )
        rows = []
        for row in queryset.iterator(chunk_size=1000):
            brand_name = str(row.get("display_brand_name") or "").strip()
            if not brand_name:
                continue
            supplier_id = row.get("autodb_supplier_id")
            brand_id = str(supplier_id or brand_name)
            rows.append(
                {
                    "id": brand_id,
                    "name": brand_name,
                    "slug": slugify(brand_name) or brand_id,
                    "logo_url": "",
                }
            )
        serializer = self.serializer_class(rows, many=True, context={"request": request})
        return Response(serializer.data)
