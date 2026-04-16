from __future__ import annotations

from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import (
    BackofficeVehicleEngineSerializer,
    BackofficeVehicleGenerationSerializer,
    BackofficeVehicleMakeSerializer,
    BackofficeVehicleModelSerializer,
    BackofficeVehicleModificationSerializer,
)
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.vehicles.models import (
    VehicleEngine,
    VehicleGeneration,
    VehicleMake,
    VehicleModel,
    VehicleModification,
)


def _parse_bool_param(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


class BackofficeTaxonomyPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 500


class BackofficeVehicleMakeListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeVehicleMakeSerializer
    pagination_class = BackofficeTaxonomyPagination
    ordering = ("name",)

    def get_queryset(self):
        queryset = VehicleMake.objects.order_by("name")
        query = self.request.query_params.get("q", "").strip()
        is_active = _parse_bool_param(self.request.query_params.get("is_active", ""))

        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(slug__icontains=query))
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        return queryset


class BackofficeVehicleMakeRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeVehicleMakeSerializer
    lookup_field = "id"

    def get_queryset(self):
        return VehicleMake.objects.order_by("name")


class BackofficeVehicleModelListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeVehicleModelSerializer
    pagination_class = BackofficeTaxonomyPagination
    ordering = ("make__name", "name")

    def get_queryset(self):
        queryset = VehicleModel.objects.select_related("make").order_by("make__name", "name")
        query = self.request.query_params.get("q", "").strip()
        make = self.request.query_params.get("make", "").strip()
        is_active = _parse_bool_param(self.request.query_params.get("is_active", ""))

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(slug__icontains=query)
                | Q(make__name__icontains=query),
            )
        if make:
            queryset = queryset.filter(make_id=make)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        return queryset


class BackofficeVehicleModelRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeVehicleModelSerializer
    lookup_field = "id"

    def get_queryset(self):
        return VehicleModel.objects.select_related("make").order_by("make__name", "name")


class BackofficeVehicleGenerationListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeVehicleGenerationSerializer
    pagination_class = BackofficeTaxonomyPagination
    ordering = ("model__make__name", "model__name", "name")

    def get_queryset(self):
        queryset = VehicleGeneration.objects.select_related("model", "model__make").order_by("model__make__name", "model__name", "name")
        query = self.request.query_params.get("q", "").strip()
        make = self.request.query_params.get("make", "").strip()
        model = self.request.query_params.get("model", "").strip()
        is_active = _parse_bool_param(self.request.query_params.get("is_active", ""))

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(model__name__icontains=query)
                | Q(model__make__name__icontains=query),
            )
        if make:
            queryset = queryset.filter(model__make_id=make)
        if model:
            queryset = queryset.filter(model_id=model)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        return queryset


class BackofficeVehicleGenerationRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeVehicleGenerationSerializer
    lookup_field = "id"

    def get_queryset(self):
        return VehicleGeneration.objects.select_related("model", "model__make").order_by("model__make__name", "model__name", "name")


class BackofficeVehicleEngineListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeVehicleEngineSerializer
    pagination_class = BackofficeTaxonomyPagination
    ordering = ("generation__model__make__name", "generation__model__name", "name")

    def get_queryset(self):
        queryset = VehicleEngine.objects.select_related("generation", "generation__model", "generation__model__make").order_by(
            "generation__model__make__name",
            "generation__model__name",
            "name",
        )
        query = self.request.query_params.get("q", "").strip()
        make = self.request.query_params.get("make", "").strip()
        model = self.request.query_params.get("model", "").strip()
        generation = self.request.query_params.get("generation", "").strip()
        fuel_type = self.request.query_params.get("fuel_type", "").strip()
        is_active = _parse_bool_param(self.request.query_params.get("is_active", ""))

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(code__icontains=query)
                | Q(generation__name__icontains=query)
                | Q(generation__model__name__icontains=query)
                | Q(generation__model__make__name__icontains=query),
            )
        if make:
            queryset = queryset.filter(generation__model__make_id=make)
        if model:
            queryset = queryset.filter(generation__model_id=model)
        if generation:
            queryset = queryset.filter(generation_id=generation)
        if fuel_type:
            queryset = queryset.filter(fuel_type=fuel_type)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        return queryset


class BackofficeVehicleEngineRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeVehicleEngineSerializer
    lookup_field = "id"

    def get_queryset(self):
        return VehicleEngine.objects.select_related("generation", "generation__model", "generation__model__make").order_by(
            "generation__model__make__name",
            "generation__model__name",
            "name",
        )


class BackofficeVehicleModificationListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeVehicleModificationSerializer
    pagination_class = BackofficeTaxonomyPagination
    ordering = ("engine__generation__model__make__name", "engine__generation__model__name", "name")

    def get_queryset(self):
        queryset = VehicleModification.objects.select_related(
            "engine",
            "engine__generation",
            "engine__generation__model",
            "engine__generation__model__make",
        ).order_by("engine__generation__model__make__name", "engine__generation__model__name", "name")
        query = self.request.query_params.get("q", "").strip()
        make = self.request.query_params.get("make", "").strip()
        model = self.request.query_params.get("model", "").strip()
        generation = self.request.query_params.get("generation", "").strip()
        engine = self.request.query_params.get("engine", "").strip()
        body_type = self.request.query_params.get("body_type", "").strip()
        transmission = self.request.query_params.get("transmission", "").strip()
        drivetrain = self.request.query_params.get("drivetrain", "").strip()
        is_active = _parse_bool_param(self.request.query_params.get("is_active", ""))

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(engine__name__icontains=query)
                | Q(engine__generation__name__icontains=query)
                | Q(engine__generation__model__name__icontains=query)
                | Q(engine__generation__model__make__name__icontains=query),
            )
        if make:
            queryset = queryset.filter(engine__generation__model__make_id=make)
        if model:
            queryset = queryset.filter(engine__generation__model_id=model)
        if generation:
            queryset = queryset.filter(engine__generation_id=generation)
        if engine:
            queryset = queryset.filter(engine_id=engine)
        if body_type:
            queryset = queryset.filter(body_type__iexact=body_type)
        if transmission:
            queryset = queryset.filter(transmission__iexact=transmission)
        if drivetrain:
            queryset = queryset.filter(drivetrain__iexact=drivetrain)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        return queryset


class BackofficeVehicleModificationRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeVehicleModificationSerializer
    lookup_field = "id"

    def get_queryset(self):
        return VehicleModification.objects.select_related(
            "engine",
            "engine__generation",
            "engine__generation__model",
            "engine__generation__model__make",
        ).order_by("engine__generation__model__make__name", "engine__generation__model__name", "name")
