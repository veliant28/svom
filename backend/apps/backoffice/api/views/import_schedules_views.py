from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework import serializers
from rest_framework.generics import ListAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import ImportSourceSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors import get_import_schedule_sources_queryset
from apps.supplier_imports.models import ImportSource


class ImportScheduleListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ImportSourceSerializer
    ordering = ("name",)

    def get_queryset(self):
        queryset = get_import_schedule_sources_queryset()
        query = self.request.query_params.get("q", "").strip()
        source_code = self.request.query_params.get("source", "").strip()
        is_enabled = self.request.query_params.get("is_auto_import_enabled", "").strip().lower()

        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(supplier__name__icontains=query))
        if source_code:
            queryset = queryset.filter(code=source_code)
        if is_enabled in {"true", "1", "yes"}:
            queryset = queryset.filter(is_auto_import_enabled=True)
        elif is_enabled in {"false", "0", "no"}:
            queryset = queryset.filter(is_auto_import_enabled=False)

        return queryset


class ImportScheduleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportSource
        fields = (
            "is_auto_import_enabled",
            "schedule_cron",
            "schedule_timezone",
            "auto_reprice_after_import",
            "auto_reindex_after_import",
            "is_active",
        )


class ImportScheduleUpdateAPIView(UpdateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ImportScheduleUpdateSerializer
    lookup_field = "id"

    def get_queryset(self):
        return get_import_schedule_sources_queryset()
