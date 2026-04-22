from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from apps.backoffice.api.serializers import BackofficeSupportAssignSerializer, BackofficeSupportStatusUpdateSerializer
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.support.api.serializers import (
    SupportCountersSerializer,
    SupportCreateMessageSerializer,
    SupportMessagesPageSerializer,
    SupportMessagesQuerySerializer,
    SupportQueueSnapshotSerializer,
    SupportThreadBootstrapSerializer,
    SupportThreadListQuerySerializer,
    SupportThreadSerializer,
    SupportWallboardSnapshotSerializer,
)
from apps.support.selectors import (
    SupportThreadFilters,
    build_queue_snapshot,
    build_user_counters,
    build_wallboard_snapshot,
    get_staff_thread,
    get_thread_messages_page,
    list_staff_threads,
    list_support_staff_users,
    serialize_message,
    serialize_thread,
    serialize_user,
)
from apps.support.services import (
    assign_support_thread,
    change_support_thread_status,
    mark_support_thread_read,
    send_support_message,
)

User = get_user_model()


class BackofficeSupportThreadListAPIView(BackofficeAPIView):
    required_capability = "customers.support"

    def get(self, request):
        query = SupportThreadListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = SupportThreadFilters(
            status=query.validated_data.get("status", ""),
            assigned_to_me=query.validated_data.get("assigned_to_me", False),
            unassigned=query.validated_data.get("unassigned", False),
            waiting=query.validated_data.get("waiting", False),
            search=query.validated_data.get("search", ""),
            ordering=query.validated_data.get("ordering", "-last_message_at"),
        )
        threads = list_staff_threads(user_id=request.user.id, filters=filters)[: query.validated_data["limit"]]
        payload = [serialize_thread(thread, current_user_id=request.user.id) for thread in threads]
        return Response({"results": SupportThreadSerializer(payload, many=True).data})


class BackofficeSupportThreadDetailAPIView(BackofficeAPIView):
    required_capability = "customers.support"

    def get(self, request, id):
        thread = get_staff_thread(user_id=request.user.id, thread_id=id)
        if thread is None:
            raise NotFound("Thread not found.")
        return Response(SupportThreadSerializer(serialize_thread(thread, current_user_id=request.user.id)).data)


class BackofficeSupportThreadMessagesAPIView(BackofficeAPIView):
    required_capability = "customers.support"

    def get(self, request, id):
        thread = get_staff_thread(user_id=request.user.id, thread_id=id)
        if thread is None:
            raise NotFound("Thread not found.")

        query = SupportMessagesQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        messages_qs = get_thread_messages_page(
            thread_id=thread.id,
            before_message_id=query.validated_data.get("before_message_id"),
        )
        limit = query.validated_data["limit"]
        page = list(messages_qs[: limit + 1])
        has_more = len(page) > limit
        results = page[:limit]
        payload = {
            "results": [serialize_message(message) for message in results],
            "has_more": has_more,
            "next_before_message_id": results[0].id if has_more and results else None,
        }
        return Response(SupportMessagesPageSerializer(payload).data)

    def post(self, request, id):
        thread = get_staff_thread(user_id=request.user.id, thread_id=id)
        if thread is None:
            raise NotFound("Thread not found.")
        serializer = SupportCreateMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        messages = send_support_message(thread=thread, author=request.user, body=serializer.validated_data["body"])
        payload = {
            "results": [serialize_message(message) for message in messages],
            "has_more": False,
            "next_before_message_id": None,
        }
        return Response(SupportMessagesPageSerializer(payload).data, status=status.HTTP_201_CREATED)


class BackofficeSupportThreadStatusAPIView(BackofficeAPIView):
    required_capability = "customers.support"

    def post(self, request, id):
        thread = get_staff_thread(user_id=request.user.id, thread_id=id)
        if thread is None:
            raise NotFound("Thread not found.")
        serializer = BackofficeSupportStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        thread = change_support_thread_status(thread=thread, status=serializer.validated_data["status"], actor=request.user)
        fresh = get_staff_thread(user_id=request.user.id, thread_id=thread.id)
        if fresh is None:
            raise NotFound("Thread not found.")
        return Response(SupportThreadSerializer(serialize_thread(fresh, current_user_id=request.user.id)).data)


class BackofficeSupportThreadAssignAPIView(BackofficeAPIView):
    required_capability = "customers.support"

    def post(self, request, id):
        thread = get_staff_thread(user_id=request.user.id, thread_id=id)
        if thread is None:
            raise NotFound("Thread not found.")
        serializer = BackofficeSupportAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assigned_staff = User.objects.filter(id=serializer.validated_data["assigned_staff_id"], is_active=True).first()
        if assigned_staff is None:
            raise ValidationError({"assigned_staff_id": "Staff user not found."})
        thread = assign_support_thread(thread=thread, assigned_staff=assigned_staff, actor=request.user)
        fresh = get_staff_thread(user_id=request.user.id, thread_id=thread.id)
        if fresh is None:
            raise NotFound("Thread not found.")
        return Response(SupportThreadSerializer(serialize_thread(fresh, current_user_id=request.user.id)).data)


class BackofficeSupportThreadReadAPIView(BackofficeAPIView):
    required_capability = "customers.support"

    def post(self, request, id):
        thread = get_staff_thread(user_id=request.user.id, thread_id=id)
        if thread is None:
            raise NotFound("Thread not found.")
        state = mark_support_thread_read(thread=thread, user=request.user)
        return Response(
            {
                "thread_id": str(thread.id),
                "last_read_message_id": str(state.last_read_message_id) if state.last_read_message_id else None,
                "last_read_at": state.last_read_at,
            }
        )


class BackofficeSupportQueueAPIView(BackofficeAPIView):
    required_capability = "customers.support"

    def get(self, request):
        return Response(SupportQueueSnapshotSerializer(build_queue_snapshot()).data)


class BackofficeSupportCountersAPIView(BackofficeAPIView):
    required_capability = "customers.support"

    def get(self, request):
        return Response(SupportCountersSerializer(build_user_counters(user=request.user)).data)


class BackofficeSupportWallboardAPIView(BackofficeAPIView):
    required_capability = "customers.support"

    def get(self, request):
        return Response(SupportWallboardSnapshotSerializer(build_wallboard_snapshot()).data)


class BackofficeSupportBootstrapAPIView(BackofficeAPIView):
    required_capability = "customers.support"

    def get(self, request):
        query = SupportThreadListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = SupportThreadFilters(
            status=query.validated_data.get("status", ""),
            assigned_to_me=query.validated_data.get("assigned_to_me", False),
            unassigned=query.validated_data.get("unassigned", False),
            waiting=query.validated_data.get("waiting", False),
            search=query.validated_data.get("search", ""),
            ordering=query.validated_data.get("ordering", "-last_message_at"),
        )
        threads = list(list_staff_threads(user_id=request.user.id, filters=filters)[: query.validated_data["limit"]])
        selected_id = request.query_params.get("thread_id")
        selected_thread = get_staff_thread(user_id=request.user.id, thread_id=selected_id) if selected_id else (threads[0] if threads else None)

        messages_payload = None
        if selected_thread is not None:
            messages = list(get_thread_messages_page(thread_id=selected_thread.id)[:51])
            has_more = len(messages) > 50
            results = messages[:50]
            messages_payload = {
                "results": [serialize_message(message) for message in results],
                "has_more": has_more,
                "next_before_message_id": results[0].id if has_more and results else None,
            }

        payload = {
            "threads": [serialize_thread(thread, current_user_id=request.user.id) for thread in threads],
            "selected_thread": serialize_thread(selected_thread, current_user_id=request.user.id) if selected_thread else None,
            "messages": messages_payload,
            "counters": build_user_counters(user=request.user),
            "queue": build_queue_snapshot(),
            "wallboard": build_wallboard_snapshot(),
        }
        return Response(SupportThreadBootstrapSerializer(payload).data)


class BackofficeSupportStaffOptionsAPIView(BackofficeAPIView):
    required_capability = "customers.support"

    def get(self, request):
        return Response({"results": [serialize_user(user) for user in list_support_staff_users()]})
