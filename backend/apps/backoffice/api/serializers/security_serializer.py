from __future__ import annotations

from rest_framework import serializers

from apps.security.models import SecurityActor, SecurityAuditLog, SecurityBlock, SecurityEvent
from apps.security.services.enforcement import SECURITY_BLOCK_MODE_HARD, SECURITY_BLOCK_MODE_SOFT, resolve_block_mode


class SecurityBlockSerializer(serializers.ModelSerializer):
    actor_source = serializers.CharField(source="actor.source_identifier", read_only=True)
    actor_status = serializers.CharField(source="actor.status", read_only=True)
    actor_threat_level = serializers.CharField(source="actor.threat_level", read_only=True)
    blocked_by_label = serializers.SerializerMethodField()
    released_by_label = serializers.SerializerMethodField()
    block_mode = serializers.SerializerMethodField()

    class Meta:
        model = SecurityBlock
        fields = (
            "id",
            "actor",
            "actor_source",
            "actor_status",
            "actor_threat_level",
            "block_type",
            "value",
            "status",
            "reason",
            "comment",
            "is_automatic",
            "block_mode",
            "blocked_by_label",
            "released_by_label",
            "blocked_at",
            "expires_at",
            "released_at",
            "release_reason",
            "metadata",
        )

    def get_blocked_by_label(self, obj: SecurityBlock) -> str:
        return obj.blocked_by.email if obj.blocked_by_id and obj.blocked_by else ""

    def get_released_by_label(self, obj: SecurityBlock) -> str:
        return obj.released_by.email if obj.released_by_id and obj.released_by else ""

    def get_block_mode(self, obj: SecurityBlock) -> str:
        return resolve_block_mode(obj)


class SecurityEventSerializer(serializers.ModelSerializer):
    actor_id = serializers.UUIDField(read_only=True)
    actor_source = serializers.CharField(source="actor.source_identifier", read_only=True)
    user_label = serializers.SerializerMethodField()
    actor_user_label = serializers.SerializerMethodField()

    class Meta:
        model = SecurityEvent
        fields = (
            "id",
            "actor_id",
            "created_at",
            "event_type",
            "severity",
            "source_ip",
            "source_kind",
            "actor_source",
            "user_label",
            "login_snapshot",
            "email_snapshot",
            "method",
            "endpoint",
            "status_code",
            "user_agent",
            "fingerprint",
            "session_key",
            "rule",
            "metadata",
            "actor_type",
            "actor_user_label",
        )

    def get_user_label(self, obj: SecurityEvent) -> str:
        return obj.user.email if obj.user_id and obj.user else ""

    def get_actor_user_label(self, obj: SecurityEvent) -> str:
        return obj.actor_user.email if obj.actor_user_id and obj.actor_user else ""


class SecurityActorSerializer(serializers.ModelSerializer):
    user_label = serializers.SerializerMethodField()
    active_block = serializers.SerializerMethodField()
    source_flags = serializers.SerializerMethodField()

    class Meta:
        model = SecurityActor
        fields = (
            "id",
            "source_ip",
            "source_identifier",
            "source_kind",
            "source_flags",
            "user",
            "user_label",
            "login_snapshot",
            "email_snapshot",
            "threat_level",
            "threat_score",
            "status",
            "block_count",
            "first_seen_at",
            "last_seen_at",
            "last_blocked_at",
            "last_unblocked_at",
            "active_block",
            "metadata",
        )

    def get_user_label(self, obj: SecurityActor) -> str:
        return obj.user.email if obj.user_id and obj.user else ""

    def get_source_flags(self, obj: SecurityActor) -> list[str]:
        raw = obj.metadata.get("source_flags", []) if isinstance(obj.metadata, dict) else []
        return [str(item) for item in raw if str(item)]

    def get_active_block(self, obj: SecurityActor) -> dict | None:
        now = self.context.get("now")
        blocks = list(getattr(obj, "blocks").all()) if hasattr(obj, "blocks") else []
        for block in sorted(blocks, key=lambda item: item.blocked_at, reverse=True):
            if block.status != SecurityBlock.STATUS_ACTIVE:
                continue
            if block.expires_at is not None and now is not None and block.expires_at <= now:
                continue
            return SecurityBlockSerializer(block).data
        return None


class SecurityActorDetailSerializer(serializers.Serializer):
    actor = SecurityActorSerializer()
    active_block = SecurityBlockSerializer(allow_null=True)
    activity_summary = serializers.DictField()
    recent_events = SecurityEventSerializer(many=True)
    top_endpoints = serializers.ListField(child=serializers.DictField())


class SecurityAuditLogSerializer(serializers.ModelSerializer):
    admin_label = serializers.SerializerMethodField()

    class Meta:
        model = SecurityAuditLog
        fields = (
            "id",
            "created_at",
            "admin_label",
            "action",
            "target_type",
            "target_id",
            "target_label",
            "old_value",
            "new_value",
            "ip",
            "user_agent",
            "comment",
        )

    def get_admin_label(self, obj: SecurityAuditLog) -> str:
        return obj.admin_user.email if obj.admin_user_id and obj.admin_user else ""


class SecurityReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(trim_whitespace=True, allow_blank=False, max_length=1000)


class SecurityCreateBlockSerializer(SecurityReasonSerializer):
    actor_id = serializers.UUIDField()
    block_mode = serializers.ChoiceField(choices=(SECURITY_BLOCK_MODE_HARD, SECURITY_BLOCK_MODE_SOFT), required=False, default=SECURITY_BLOCK_MODE_HARD)


class SecurityExtendBlockSerializer(serializers.Serializer):
    minutes = serializers.IntegerField(min_value=1, max_value=525600)
    reason = serializers.CharField(trim_whitespace=True, allow_blank=False, max_length=1000)
    block_mode = serializers.ChoiceField(choices=(SECURITY_BLOCK_MODE_HARD, SECURITY_BLOCK_MODE_SOFT), required=False)


class SecurityCommentSerializer(serializers.Serializer):
    comment = serializers.CharField(trim_whitespace=True, allow_blank=False, max_length=2000)
