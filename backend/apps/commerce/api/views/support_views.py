from __future__ import annotations

from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.support.api.serializers import (
    SupportCountersSerializer,
    SupportCreateMessageSerializer,
    SupportCreateThreadSerializer,
    SupportMessagesPageSerializer,
    SupportMessagesQuerySerializer,
    SupportThreadBootstrapSerializer,
    SupportThreadListQuerySerializer,
    SupportThreadSerializer,
)
from apps.support.selectors import (
    SupportThreadFilters,
    build_user_counters,
    get_customer_thread,
    get_thread_messages_page,
    list_customer_threads,
    serialize_message,
    serialize_thread,
)
from apps.support.services import create_support_thread, mark_support_thread_read, send_support_message

class CommerceSupportAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]


class SupportThreadListCreateAPIView(CommerceSupportAPIView):
    def get(self, request):
        query = SupportThreadListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = SupportThreadFilters(
            status=query.validated_data.get("status", ""),
            waiting=query.validated_data.get("waiting", False),
            search=query.validated_data.get("search", ""),
            ordering=query.validated_data.get("ordering", "-last_message_at"),
        )
        threads = list_customer_threads(customer_id=request.user.id, filters=filters)[: query.validated_data["limit"]]
        payload = [serialize_thread(thread, current_user_id=request.user.id) for thread in threads]
        return Response({"results": SupportThreadSerializer(payload, many=True).data})

    def post(self, request):
        serializer = SupportCreateThreadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        thread, _message = create_support_thread(
            customer=request.user,
            subject=serializer.validated_data["subject"],
            body=serializer.validated_data["body"],
        )
        fresh_thread = get_customer_thread(customer_id=request.user.id, thread_id=thread.id)
        if fresh_thread is None:
            raise NotFound("Thread was not created.")
        payload = serialize_thread(fresh_thread, current_user_id=request.user.id)
        return Response(SupportThreadSerializer(payload).data, status=status.HTTP_201_CREATED)


class SupportThreadDetailAPIView(CommerceSupportAPIView):
    def get(self, request, id):
        thread = get_customer_thread(customer_id=request.user.id, thread_id=id)
        if thread is None:
            raise NotFound("Thread not found.")
        return Response(SupportThreadSerializer(serialize_thread(thread, current_user_id=request.user.id)).data)


class SupportThreadMessagesAPIView(CommerceSupportAPIView):
    def get(self, request, id):
        thread = get_customer_thread(customer_id=request.user.id, thread_id=id)
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
        next_before = results[0].id if has_more and results else None
        payload = {
            "results": [serialize_message(message) for message in results],
            "has_more": has_more,
            "next_before_message_id": next_before,
        }
        return Response(SupportMessagesPageSerializer(payload).data)

    def post(self, request, id):
        thread = get_customer_thread(customer_id=request.user.id, thread_id=id)
        if thread is None:
            raise NotFound("Thread not found.")
        serializer = SupportCreateMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        messages = send_support_message(thread=thread, author=request.user, body=serializer.validated_data["body"])
        if not messages:
            raise ValidationError({"detail": "Message was not created."})
        payload = {
            "results": [serialize_message(item) for item in messages],
            "has_more": False,
            "next_before_message_id": None,
        }
        return Response(SupportMessagesPageSerializer(payload).data, status=status.HTTP_201_CREATED)


class SupportThreadReadAPIView(CommerceSupportAPIView):
    def post(self, request, id):
        thread = get_customer_thread(customer_id=request.user.id, thread_id=id)
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


class SupportBootstrapAPIView(CommerceSupportAPIView):
    def get(self, request):
        query = SupportThreadListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = SupportThreadFilters(
            status=query.validated_data.get("status", ""),
            waiting=query.validated_data.get("waiting", False),
            search=query.validated_data.get("search", ""),
            ordering=query.validated_data.get("ordering", "-last_message_at"),
        )
        threads = list(list_customer_threads(customer_id=request.user.id, filters=filters)[: query.validated_data["limit"]])
        selected_id = request.query_params.get("thread_id")
        selected_thread = get_customer_thread(customer_id=request.user.id, thread_id=selected_id) if selected_id else (threads[0] if threads else None)

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
        }
        return Response(
            SupportThreadBootstrapSerializer(payload).data
        )
