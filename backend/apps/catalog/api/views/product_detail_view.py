from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response

from apps.catalog.models import Product
from apps.catalog.api.serializers import ProductDetailSerializer
from apps.catalog.selectors import get_product_detail_queryset


class ProductDetailAPIView(RetrieveAPIView):
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return get_product_detail_queryset()

    def _resolve_product_id(self, lookup_value: str):
        by_slug_id = (
            Product.objects.filter(is_active=True, slug=lookup_value)
            .values_list("id", flat=True)
            .first()
        )
        if by_slug_id is not None:
            return by_slug_id

        candidate = (
            Product.objects.filter(is_active=True)
            .filter(
                Q(slug__iexact=lookup_value)
                | Q(article__iexact=lookup_value)
                | Q(autodb_article_number__iexact=lookup_value)
                | Q(sku__iexact=lookup_value)
                | Q(svom_sku__iexact=lookup_value)
            )
            .order_by("-updated_at", "id")
            .values_list("id", flat=True)
            .first()
        )
        return candidate

    def get_object(self):
        lookup_value = str(self.kwargs.get(self.lookup_field) or "").strip()
        if not lookup_value:
            raise Http404("Product slug is required.")

        product_id = self._resolve_product_id(lookup_value)
        if product_id is None:
            raise Http404("Product not found.")

        queryset = get_product_detail_queryset().filter(id=product_id)
        return get_object_or_404(queryset, id=product_id)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
