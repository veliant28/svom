from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import SupplierBrandAliasSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors import get_supplier_brand_aliases_queryset


class BrandAliasListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = SupplierBrandAliasSerializer
    ordering = ("-priority", "supplier_brand_alias")

    def get_queryset(self):
        queryset = get_supplier_brand_aliases_queryset()
        query = self.request.query_params.get("q", "").strip()
        source_code = self.request.query_params.get("source", "").strip()
        supplier_code = self.request.query_params.get("supplier", "").strip()
        is_active = self.request.query_params.get("is_active", "").strip().lower()
        if query:
            queryset = queryset.filter(
                Q(supplier_brand_alias__icontains=query)
                | Q(normalized_alias__icontains=query)
                | Q(canonical_brand_name__icontains=query)
                | Q(canonical_brand__name__icontains=query)
            )
        if source_code:
            queryset = queryset.filter(source__code=source_code)
        if supplier_code:
            queryset = queryset.filter(supplier__code=supplier_code)
        if is_active in {"true", "1", "yes"}:
            queryset = queryset.filter(is_active=True)
        elif is_active in {"false", "0", "no"}:
            queryset = queryset.filter(is_active=False)
        return queryset


class BrandAliasRetrieveUpdateAPIView(RetrieveUpdateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = SupplierBrandAliasSerializer
    lookup_field = "id"

    def get_queryset(self):
        return get_supplier_brand_aliases_queryset()
