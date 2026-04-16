from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import ImportQualitySummarySerializer, ImportRunQualitySerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors import (
    build_import_quality_summary_payload,
    build_run_quality_comparison_payload,
    get_import_quality_queryset,
)
from apps.supplier_imports.models import ImportRun
from apps.supplier_imports.services import ImportQualityService


class ImportQualitySummaryAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]

    def get(self, request):
        payload = build_import_quality_summary_payload()
        serializer = ImportQualitySummarySerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ImportQualityListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ImportRunQualitySerializer
    ordering = ("-created_at",)

    def get_queryset(self):
        queryset = get_import_quality_queryset()
        source = self.request.query_params.get("source", "").strip()
        status = self.request.query_params.get("status", "").strip()
        requires_attention = self.request.query_params.get("requires_attention", "").strip().lower()
        query = self.request.query_params.get("q", "").strip()

        if source:
            queryset = queryset.filter(source__code=source)
        if status:
            queryset = queryset.filter(status=status)
        if requires_attention in {"true", "1", "yes"}:
            queryset = queryset.filter(requires_operator_attention=True)
        elif requires_attention in {"false", "0", "no"}:
            queryset = queryset.filter(requires_operator_attention=False)
        if query:
            queryset = queryset.filter(Q(source__code__icontains=query) | Q(source__name__icontains=query))
        return queryset


class ImportQualityDetailAPIView(RetrieveAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ImportRunQualitySerializer
    lookup_field = "run_id"

    def get_queryset(self):
        return get_import_quality_queryset()

    def get_object(self):
        run_id = self.kwargs["run_id"]
        run = get_object_or_404(ImportRun.objects.select_related("source"), id=run_id)
        quality = ImportQualityService().refresh_for_run(run=run).quality
        return quality


class ImportQualityCompareAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]

    def get(self, request, run_id: str):
        run = get_object_or_404(ImportRun.objects.select_related("source"), id=run_id)
        ImportQualityService().refresh_for_run(run=run)
        payload = build_run_quality_comparison_payload(run=run)
        return Response(payload, status=status.HTTP_200_OK)
