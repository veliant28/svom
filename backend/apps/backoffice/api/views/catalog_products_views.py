from django.db.models import Q
from django.db.models import Prefetch
from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.backoffice.api.serializers import BackofficeCatalogProductSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.catalog.models import Product
from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer


class BackofficeCatalogProductPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 500


def _parse_bool_param(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


class BackofficeCatalogProductListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeCatalogProductSerializer
    ordering = ("name",)
    pagination_class = BackofficeCatalogProductPagination

    @staticmethod
    def _supplier_offers_prefetch() -> Prefetch:
        return Prefetch(
            "supplier_offers",
            queryset=SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "-updated_at", "id"),
            to_attr="backoffice_supplier_offers",
        )

    @staticmethod
    def _raw_offers_prefetch() -> Prefetch:
        return Prefetch(
            "raw_supplier_offers",
            queryset=SupplierRawOffer.objects.select_related("source", "supplier").order_by("supplier__priority", "source__code", "-updated_at", "-id"),
            to_attr="backoffice_raw_offers",
        )

    def get_queryset(self):
        queryset = (
            Product.objects.select_related("brand", "category", "product_price", "product_price__policy")
            .prefetch_related(self._supplier_offers_prefetch(), self._raw_offers_prefetch())
            .order_by("name")
        )
        query = self.request.query_params.get("q", "").strip()
        brand = self.request.query_params.get("brand", "").strip()
        category = self.request.query_params.get("category", "").strip()

        is_active = _parse_bool_param(self.request.query_params.get("is_active", ""))
        is_featured = _parse_bool_param(self.request.query_params.get("is_featured", ""))
        is_new = _parse_bool_param(self.request.query_params.get("is_new", ""))
        is_bestseller = _parse_bool_param(self.request.query_params.get("is_bestseller", ""))

        if query:
            queryset = queryset.filter(
                Q(sku__icontains=query)
                | Q(article__icontains=query)
                | Q(name__icontains=query)
                | Q(slug__icontains=query)
                | Q(brand__name__icontains=query)
                | Q(category__name__icontains=query),
            )
        if brand:
            queryset = queryset.filter(brand_id=brand)
        if category:
            queryset = queryset.filter(category_id=category)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        if is_featured is not None:
            queryset = queryset.filter(is_featured=is_featured)
        if is_new is not None:
            queryset = queryset.filter(is_new=is_new)
        if is_bestseller is not None:
            queryset = queryset.filter(is_bestseller=is_bestseller)

        return queryset


class BackofficeCatalogProductRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeCatalogProductSerializer
    lookup_field = "id"

    def get_queryset(self):
        supplier_offers_prefetch = Prefetch(
            "supplier_offers",
            queryset=SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "-updated_at", "id"),
            to_attr="backoffice_supplier_offers",
        )
        raw_offers_prefetch = Prefetch(
            "raw_supplier_offers",
            queryset=SupplierRawOffer.objects.select_related("source", "supplier").order_by("supplier__priority", "source__code", "-updated_at", "-id"),
            to_attr="backoffice_raw_offers",
        )
        return (
            Product.objects.select_related("brand", "category", "product_price", "product_price__policy")
            .prefetch_related(supplier_offers_prefetch, raw_offers_prefetch)
            .order_by("name")
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            detail = "Товар нельзя удалить: есть связанные записи."
            return Response({"detail": detail, "linked_product_id": str(instance.id)}, status=status.HTTP_409_CONFLICT)
