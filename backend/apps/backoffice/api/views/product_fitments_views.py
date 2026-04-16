from __future__ import annotations

from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import BackofficeProductFitmentSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.compatibility.models import ProductFitment


def _parse_bool_param(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


class BackofficeProductFitmentPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 500


class BackofficeProductFitmentListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeProductFitmentSerializer
    pagination_class = BackofficeProductFitmentPagination
    ordering = ("product__name",)

    def get_queryset(self):
        queryset = ProductFitment.objects.select_related(
            "product",
            "modification",
            "modification__engine",
            "modification__engine__generation",
            "modification__engine__generation__model",
            "modification__engine__generation__model__make",
        ).order_by("product__name")
        query = self.request.query_params.get("q", "").strip()
        product = self.request.query_params.get("product", "").strip()
        modification = self.request.query_params.get("modification", "").strip()
        make = self.request.query_params.get("make", "").strip()
        model = self.request.query_params.get("model", "").strip()
        generation = self.request.query_params.get("generation", "").strip()
        engine = self.request.query_params.get("engine", "").strip()
        is_exact = _parse_bool_param(self.request.query_params.get("is_exact", ""))

        if query:
            queryset = queryset.filter(
                Q(product__name__icontains=query)
                | Q(product__sku__icontains=query)
                | Q(product__article__icontains=query)
                | Q(modification__name__icontains=query)
                | Q(modification__engine__name__icontains=query)
                | Q(modification__engine__generation__name__icontains=query)
                | Q(modification__engine__generation__model__name__icontains=query)
                | Q(modification__engine__generation__model__make__name__icontains=query),
            )
        if product:
            queryset = queryset.filter(product_id=product)
        if modification:
            queryset = queryset.filter(modification_id=modification)
        if make:
            queryset = queryset.filter(modification__engine__generation__model__make_id=make)
        if model:
            queryset = queryset.filter(modification__engine__generation__model_id=model)
        if generation:
            queryset = queryset.filter(modification__engine__generation_id=generation)
        if engine:
            queryset = queryset.filter(modification__engine_id=engine)
        if is_exact is not None:
            queryset = queryset.filter(is_exact=is_exact)

        return queryset


class BackofficeProductFitmentRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeProductFitmentSerializer
    lookup_field = "id"

    def get_queryset(self):
        return ProductFitment.objects.select_related(
            "product",
            "modification",
            "modification__engine",
            "modification__engine__generation",
            "modification__engine__generation__model",
            "modification__engine__generation__model__make",
        ).order_by("product__name")
