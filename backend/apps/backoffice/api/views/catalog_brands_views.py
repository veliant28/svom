from django.db.models import Q
from django.db.models.deletion import ProtectedError
from rest_framework.authentication import TokenAuthentication
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.backoffice.api.serializers import BackofficeCatalogBrandSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.catalog.models import Brand


class BackofficeCatalogBrandListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeCatalogBrandSerializer
    ordering = ("name",)

    def get_queryset(self):
        queryset = Brand.objects.all().order_by("name")
        query = self.request.query_params.get("q", "").strip()
        is_active = self.request.query_params.get("is_active", "").strip().lower()
        imported_from = self.request.query_params.get("imported_from", "").strip()

        if query:
            queryset = queryset.filter(Q(name__icontains=query))
        if is_active in {"true", "1", "yes"}:
            queryset = queryset.filter(is_active=True)
        elif is_active in {"false", "0", "no"}:
            queryset = queryset.filter(is_active=False)
        if imported_from:
            queryset = queryset.filter(supplier_brand_aliases__source__code=imported_from).distinct()
        return queryset


class BackofficeCatalogBrandRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeCatalogBrandSerializer
    lookup_field = "id"

    def get_queryset(self):
        return Brand.objects.all().order_by("name")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            linked_products = instance.products.count()
            detail = "Бренд нельзя удалить: есть связанные товары."
            if linked_products:
                detail = f"Бренд нельзя удалить: связано товаров {linked_products}."
            return Response(
                {
                    "detail": detail,
                    "linked_products": linked_products,
                },
                status=status.HTTP_409_CONFLICT,
            )
