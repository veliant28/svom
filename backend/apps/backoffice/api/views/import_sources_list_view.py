from django.db.models import Q
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication

from apps.backoffice.api.serializers import ImportSourceSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors import get_import_sources_queryset


class ImportSourceListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ImportSourceSerializer
    ordering = ("name",)

    def get_queryset(self):
        queryset = get_import_sources_queryset()
        query = self.request.query_params.get("q", "").strip()
        is_active = self.request.query_params.get("is_active", "").strip().lower()

        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(supplier__name__icontains=query))

        if is_active in {"true", "1", "yes"}:
            queryset = queryset.filter(is_active=True)
        elif is_active in {"false", "0", "no"}:
            queryset = queryset.filter(is_active=False)

        return queryset
