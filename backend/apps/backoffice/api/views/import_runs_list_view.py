from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import ImportRunSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors.imports_selectors import apply_import_run_filters, get_import_runs_queryset


class ImportRunListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ImportRunSerializer
    ordering = ("-created_at",)

    def get_queryset(self):
        queryset = get_import_runs_queryset()
        queryset = apply_import_run_filters(queryset, params=self.request.query_params)

        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(source__code__icontains=query)
                | Q(source__name__icontains=query)
                | Q(status__icontains=query)
                | Q(trigger__icontains=query)
            )

        return queryset
