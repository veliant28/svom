from __future__ import annotations

from rest_framework import serializers

from apps.support.models import SupportThread

PUBLIC_STATUS_CHOICES = (
    (SupportThread.STATUS_NEW, "new"),
    (SupportThread.STATUS_OPEN, "open"),
    (SupportThread.STATUS_RESOLVED, "resolved"),
    (SupportThread.STATUS_CLOSED, "closed"),
)


class SupportUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    is_online = serializers.BooleanField()


class SupportMessageSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    thread_id = serializers.UUIDField()
    author = SupportUserSerializer(allow_null=True)
    author_side = serializers.CharField()
    kind = serializers.CharField()
    body = serializers.CharField()
    event_code = serializers.CharField(allow_blank=True)
    event_payload = serializers.JSONField()
    created_at = serializers.DateTimeField()
    edited_at = serializers.DateTimeField(allow_null=True)


class SupportThreadSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    subject = serializers.CharField()
    status = serializers.CharField()
    priority = serializers.CharField()
    customer = SupportUserSerializer()
    assigned_staff = SupportUserSerializer(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    last_message_at = serializers.DateTimeField(allow_null=True)
    first_response_at = serializers.DateTimeField(allow_null=True)
    resolved_at = serializers.DateTimeField(allow_null=True)
    closed_at = serializers.DateTimeField(allow_null=True)
    latest_message_id = serializers.UUIDField(allow_null=True)
    latest_message_preview = serializers.CharField(allow_blank=True)
    latest_message_author_side = serializers.CharField(allow_blank=True)
    is_waiting = serializers.BooleanField()
    unread_count = serializers.IntegerField(required=False)
    is_mine = serializers.BooleanField(required=False)


class SupportMessagesPageSerializer(serializers.Serializer):
    results = SupportMessageSerializer(many=True)
    has_more = serializers.BooleanField()
    next_before_message_id = serializers.UUIDField(allow_null=True)


class SupportQueueSnapshotSerializer(serializers.Serializer):
    new = serializers.IntegerField()
    open = serializers.IntegerField()
    waiting_for_support = serializers.IntegerField()
    waiting_for_client = serializers.IntegerField()
    resolved = serializers.IntegerField()
    closed = serializers.IntegerField()
    unassigned = serializers.IntegerField()
    latest_threads = SupportThreadSerializer(many=True)


class SupportWallboardOperatorSerializer(serializers.Serializer):
    user = SupportUserSerializer()
    active_threads = serializers.IntegerField()


class SupportWallboardSnapshotSerializer(serializers.Serializer):
    counts = serializers.DictField(child=serializers.IntegerField())
    threads_per_operator = SupportWallboardOperatorSerializer(many=True)
    oldest_waiting = SupportThreadSerializer(allow_null=True)
    latest_active_threads = SupportThreadSerializer(many=True)
    avg_first_response_seconds = serializers.IntegerField(allow_null=True)


class SupportCountersSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    total_unread_threads = serializers.IntegerField()
    assigned_to_me = serializers.IntegerField(required=False)
    unassigned = serializers.IntegerField(required=False)
    open_threads = serializers.IntegerField(required=False)


class SupportTypingPayloadSerializer(serializers.Serializer):
    thread_id = serializers.CharField()
    customer_users = SupportUserSerializer(many=True)
    staff_users = SupportUserSerializer(many=True)


class SupportThreadListQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=PUBLIC_STATUS_CHOICES, required=False, allow_blank=True)
    assigned_to_me = serializers.BooleanField(required=False, default=False)
    unassigned = serializers.BooleanField(required=False, default=False)
    waiting = serializers.BooleanField(required=False, default=False)
    search = serializers.CharField(required=False, allow_blank=True)
    ordering = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20)


class SupportCreateThreadSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255)
    body = serializers.CharField()


class SupportCreateMessageSerializer(serializers.Serializer):
    body = serializers.CharField()


class SupportMessagesQuerySerializer(serializers.Serializer):
    before_message_id = serializers.UUIDField(required=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=50)


class SupportStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=PUBLIC_STATUS_CHOICES)


class SupportAssignSerializer(serializers.Serializer):
    assigned_staff_id = serializers.IntegerField(min_value=1)


class SupportThreadBootstrapSerializer(serializers.Serializer):
    threads = SupportThreadSerializer(many=True)
    selected_thread = SupportThreadSerializer(allow_null=True)
    messages = SupportMessagesPageSerializer(allow_null=True)
    counters = SupportCountersSerializer()
    queue = SupportQueueSnapshotSerializer(required=False)
    wallboard = SupportWallboardSnapshotSerializer(required=False)
