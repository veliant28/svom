from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.generics import RetrieveAPIView

from apps.catalog.models import Product
from apps.catalog.api.serializers import ProductDetailSerializer
from apps.catalog.selectors import get_product_detail_queryset
from apps.catalog.services import FITMENT_ALL, FitmentFilteringService


class ProductDetailAPIView(RetrieveAPIView):
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        params = self.request.query_params.copy()
        params["fitment"] = FITMENT_ALL
        queryset, _ = FitmentFilteringService().apply(
            queryset=get_product_detail_queryset(),
            params=params,
        )
        return queryset

    def get_object(self):
        queryset = self.get_queryset()
        lookup_value = str(self.kwargs.get(self.lookup_field) or "").strip()
        if not lookup_value:
            raise Http404("Product slug is required.")

        # Primary lookup path keeps canonical URL behavior.
        by_slug = queryset.filter(slug=lookup_value).first()
        if by_slug is not None:
            return by_slug

        # Safe fallback for stale links where article/SKU was used instead of slug.
        candidates = Product.objects.filter(is_active=True).filter(
            Q(slug__iexact=lookup_value)
            | Q(article__iexact=lookup_value)
            | Q(autodb_article_number__iexact=lookup_value)
            | Q(sku__iexact=lookup_value)
            | Q(svom_sku__iexact=lookup_value)
        )
        candidate = candidates.order_by("-updated_at", "id").first()
        if candidate is None:
            raise Http404("Product not found.")

        return get_object_or_404(queryset, id=candidate.id)
