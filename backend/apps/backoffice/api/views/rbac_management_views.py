from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.backoffice.api.serializers.backoffice_group_rbac_serializer import (
    BackofficeGroupCreateSerializer,
    BackofficeGroupDetailSerializer,
    BackofficeGroupListSerializer,
    BackofficeGroupUpdateSerializer,
)
from apps.backoffice.api.serializers.backoffice_user_rbac_serializer import (
    BackofficeUserCreateSerializer,
    BackofficeUserDetailSerializer,
    BackofficeUserListSerializer,
    BackofficeUserUpdateSerializer,
)
from apps.backoffice.api.serializers.rbac_meta_serializer import BackofficeRbacMetaSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.users.rbac import (
    ensure_system_groups_exist,
    get_user_system_role,
    list_backoffice_capability_payloads,
    list_system_role_payloads,
)


User = get_user_model()


def _parse_bool_param(value: str) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


class BackofficeRbacMetaAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    required_capability = "users.view"

    def get(self, request):
        ensure_system_groups_exist()
        serializer = BackofficeRbacMetaSerializer(
            {
                "roles": list_system_role_payloads(),
                "capabilities": list_backoffice_capability_payloads(),
            }
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class BackofficeUserListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BackofficeUserCreateSerializer
        return BackofficeUserListSerializer

    def get_queryset(self):
        queryset = User.objects.all().prefetch_related("groups").order_by("-date_joined", "email")

        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(email__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(middle_name__icontains=query)
                | Q(phone__icontains=query)
            )

        is_active = _parse_bool_param(self.request.query_params.get("is_active", ""))
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        group_id_raw = self.request.query_params.get("group_id", "").strip()
        if group_id_raw.isdigit():
            queryset = queryset.filter(groups__id=int(group_id_raw))

        system_role = self.request.query_params.get("system_role", "").strip().lower()
        if system_role:
            ensure_system_groups_exist()
            group_name = f"Backoffice Role: {system_role}"
            queryset = queryset.filter(groups__name=group_name)

        return queryset.distinct()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        payload = BackofficeUserDetailSerializer(user).data
        return Response(payload, status=status.HTTP_201_CREATED)


class BackofficeUserRetrieveUpdateAPIView(RetrieveUpdateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    lookup_field = "id"

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return BackofficeUserUpdateSerializer
        return BackofficeUserDetailSerializer

    def get_queryset(self):
        return User.objects.all().prefetch_related("groups")

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        payload = BackofficeUserDetailSerializer(instance).data
        return Response(payload, status=status.HTTP_200_OK)


class BackofficeUserActivateAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.is_active = True
        user.save(update_fields=("is_active", "updated_at"))
        return Response(BackofficeUserDetailSerializer(user).data, status=status.HTTP_200_OK)


class BackofficeUserDeactivateAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.is_active = False
        user.save(update_fields=("is_active", "updated_at"))
        return Response(BackofficeUserDetailSerializer(user).data, status=status.HTTP_200_OK)


class BackofficeGroupListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BackofficeGroupCreateSerializer
        return BackofficeGroupListSerializer

    def get_queryset(self):
        queryset = Group.objects.all().annotate(members_count=Count("user")).order_by("name")
        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset

    def create(self, request, *args, **kwargs):
        if get_user_system_role(request.user) != "administrator":
            return Response({"detail": "Only administrator can create groups."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = serializer.save()
        payload = BackofficeGroupDetailSerializer(group).data
        return Response(payload, status=status.HTTP_201_CREATED)


class BackofficeGroupRetrieveUpdateAPIView(RetrieveUpdateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    lookup_field = "id"
    queryset = Group.objects.all().annotate(members_count=Count("user")).order_by("name")

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return BackofficeGroupUpdateSerializer
        return BackofficeGroupDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.method in {"PUT", "PATCH"}:
            context["group"] = self.get_object()
        return context

    def update(self, request, *args, **kwargs):
        group = self.get_object()
        serializer = self.get_serializer(group, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        group.refresh_from_db()
        return Response(BackofficeGroupDetailSerializer(group).data, status=status.HTTP_200_OK)
