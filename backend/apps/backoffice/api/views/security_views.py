from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.backoffice.api.serializers.security_serializer import (
    SecurityActorDetailSerializer,
    SecurityActorSerializer,
    SecurityAuditLogSerializer,
    SecurityBlockSerializer,
    SecurityCommentSerializer,
    SecurityCreateBlockSerializer,
    SecurityEventSerializer,
    SecurityExtendBlockSerializer,
    SecurityReasonSerializer,
)
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.security.models import SecurityActor, SecurityBlock
from apps.security.services import (
    add_actor_comment,
    create_manual_block,
    extend_block,
    get_security_actor_detail,
    list_security_actor_history,
    list_security_actors,
    list_security_audit_logs,
    list_security_blocks,
    mark_false_positive,
    release_block,
    security_summary,
    security_timeseries,
    whitelist_actor,
)


class SecurityPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class SecuritySummaryAPIView(BackofficeAPIView):
    required_capability = "security.view"

    def get(self, request):
        data = security_summary()
        return Response(
            {
                "kpis": {key: data[key] for key in ("active_blocks", "suspicious_sources", "blocked_24h", "failed_logins", "rate_limit_events", "critical_threats")},
                "latest_critical_events": SecurityEventSerializer(data["latest_critical_events"], many=True).data,
                "active_blocks": SecurityBlockSerializer(data["active_block_rows"], many=True).data,
            }
        )


class SecurityTimeseriesAPIView(BackofficeAPIView):
    required_capability = "security.view"

    def get(self, request):
        return Response(security_timeseries())


class SecurityActorListAPIView(BackofficeAPIView):
    required_capability = "security.view"
    pagination_class = SecurityPagination

    def get(self, request):
        qs = list_security_actors(
            query=request.query_params.get("q", "").strip(),
            status=request.query_params.get("status", "").strip(),
            threat_level=request.query_params.get("threat_level", "").strip(),
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = SecurityActorSerializer(page, many=True, context={"now": timezone.now()})
        return paginator.get_paginated_response(serializer.data)


class SecurityActorDetailAPIView(BackofficeAPIView):
    required_capability = "security.view"

    def get(self, request, id):
        detail = get_security_actor_detail(actor_id=id)
        return Response(SecurityActorDetailSerializer(detail, context={"now": timezone.now()}).data)


class SecurityActorHistoryAPIView(BackofficeAPIView):
    required_capability = "security.view"

    def get(self, request, id):
        events = list_security_actor_history(actor_id=id)
        return Response({"results": SecurityEventSerializer(events, many=True).data})


class SecurityBlockListCreateAPIView(BackofficeAPIView):
    def get_permissions(self):
        self.required_capability = "security.view" if self.request.method == "GET" else "security.respond"
        return super().get_permissions()

    def get(self, request):
        return Response({"results": SecurityBlockSerializer(list_security_blocks()[:100], many=True).data})

    def post(self, request):
        serializer = SecurityCreateBlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = get_object_or_404(SecurityActor, id=serializer.validated_data["actor_id"])
        block = create_manual_block(
            actor=actor,
            request=request,
            reason=serializer.validated_data["reason"],
            mode=serializer.validated_data.get("block_mode"),
        )
        return Response(SecurityBlockSerializer(block).data, status=201)


class SecurityBlockReleaseAPIView(BackofficeAPIView):
    required_capability = "security.respond"

    def post(self, request, id):
        serializer = SecurityReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        block = get_object_or_404(SecurityBlock.objects.select_related("actor"), id=id)
        block = release_block(block=block, request=request, reason=serializer.validated_data["reason"])
        return Response(SecurityBlockSerializer(block).data)


class SecurityBlockWhitelistAPIView(BackofficeAPIView):
    required_capability = "security.respond"

    def post(self, request, id):
        serializer = SecurityReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        block = get_object_or_404(SecurityBlock.objects.select_related("actor"), id=id)
        actor = whitelist_actor(actor=block.actor, request=request, reason=serializer.validated_data["reason"])
        return Response(SecurityActorSerializer(actor, context={"now": timezone.now()}).data)


class SecurityBlockExtendAPIView(BackofficeAPIView):
    required_capability = "security.respond"

    def post(self, request, id):
        serializer = SecurityExtendBlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        block = get_object_or_404(SecurityBlock.objects.select_related("actor"), id=id)
        block = extend_block(
            block=block,
            request=request,
            minutes=serializer.validated_data["minutes"],
            reason=serializer.validated_data["reason"],
            mode=serializer.validated_data.get("block_mode"),
        )
        return Response(SecurityBlockSerializer(block).data)


class SecurityActorCommentAPIView(BackofficeAPIView):
    required_capability = "security.respond"

    def post(self, request, id):
        serializer = SecurityCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = get_object_or_404(SecurityActor, id=id)
        add_actor_comment(actor=actor, request=request, comment=serializer.validated_data["comment"])
        return Response(SecurityActorSerializer(actor, context={"now": timezone.now()}).data)


class SecurityActorFalsePositiveAPIView(BackofficeAPIView):
    required_capability = "security.respond"

    def post(self, request, id):
        serializer = SecurityReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = get_object_or_404(SecurityActor, id=id)
        actor = mark_false_positive(actor=actor, request=request, reason=serializer.validated_data["reason"])
        return Response(SecurityActorSerializer(actor, context={"now": timezone.now()}).data)


class SecurityAuditListAPIView(BackofficeAPIView):
    required_capability = "security.audit"

    def get(self, request):
        return Response({"results": SecurityAuditLogSerializer(list_security_audit_logs(), many=True).data})
