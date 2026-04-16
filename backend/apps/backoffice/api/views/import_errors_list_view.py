from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import ImportRowErrorSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors.imports_selectors import apply_import_error_filters, get_import_errors_queryset


class ImportRowErrorListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ImportRowErrorSerializer
    ordering = ("-created_at",)

    def get_queryset(self):
        queryset = get_import_errors_queryset()
        queryset = apply_import_error_filters(queryset, params=self.request.query_params)

        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(error_code__icontains=query)
                | Q(message__icontains=query)
                | Q(external_sku__icontains=query)
                | Q(source__code__icontains=query)
            )

        return queryset
