from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.autocatalog.api.serializers import (
    AutocatalogGarageCapacitySerializer,
    AutocatalogGarageEngineSerializer,
    AutocatalogGarageMakeSerializer,
    AutocatalogGarageModelSerializer,
    AutocatalogGarageModificationSerializer,
    AutocatalogGarageYearSerializer,
)
from apps.autocatalog.selectors import (
    get_autocatalog_engine_options,
    get_autocatalog_garage_capacities,
    get_autocatalog_garage_makes_queryset,
    get_autocatalog_garage_models_queryset,
    get_autocatalog_garage_modification_names,
    get_autocatalog_garage_years,
)


class AutocatalogGarageMakeListAPIView(ListAPIView):
    serializer_class = AutocatalogGarageMakeSerializer
    pagination_class = None

    def get_queryset(self):
        year_param = self.request.query_params.get("year")
        try:
            year = int(year_param) if year_param is not None else None
        except (TypeError, ValueError):
            year = None
        return get_autocatalog_garage_makes_queryset(year=year)


class AutocatalogGarageModelListAPIView(ListAPIView):
    serializer_class = AutocatalogGarageModelSerializer
    pagination_class = None

    def get_queryset(self):
        year_param = self.request.query_params.get("year")
        try:
            year = int(year_param) if year_param is not None else None
        except (TypeError, ValueError):
            year = None
        return get_autocatalog_garage_models_queryset(
            make_id=self.request.query_params.get("make", "").strip(),
            year=year,
        )


class AutocatalogGarageYearListAPIView(APIView):
    def get(self, request):
        years = get_autocatalog_garage_years(
            make_id=request.query_params.get("make", "").strip(),
            model_id=request.query_params.get("model", "").strip(),
            modification=request.query_params.get("modification", "").strip(),
            capacity=request.query_params.get("capacity", "").strip(),
            engine=request.query_params.get("engine", "").strip(),
        )
        serializer = AutocatalogGarageYearSerializer([{"year": year} for year in years], many=True)
        return Response(serializer.data)


class AutocatalogGarageModificationListAPIView(APIView):
    def get(self, request):
        year_param = request.query_params.get("year")
        try:
            year = int(year_param) if year_param is not None else None
        except (TypeError, ValueError):
            year = None

        modifications = get_autocatalog_garage_modification_names(
            make_id=request.query_params.get("make", "").strip(),
            model_id=request.query_params.get("model", "").strip(),
            year=year,
        )
        serializer = AutocatalogGarageModificationSerializer(
            [{"modification": modification} for modification in modifications],
            many=True,
        )
        return Response(serializer.data)


class AutocatalogGarageEngineListAPIView(ListAPIView):
    serializer_class = AutocatalogGarageEngineSerializer
    pagination_class = None

    def get_queryset(self):
        year_param = self.request.query_params.get("year")
        try:
            year = int(year_param) if year_param is not None else None
        except (TypeError, ValueError):
            year = None

        return get_autocatalog_engine_options(
            make_id=self.request.query_params.get("make", "").strip(),
            model_id=self.request.query_params.get("model", "").strip(),
            year=year,
            modification=self.request.query_params.get("modification", "").strip(),
            capacity=self.request.query_params.get("capacity", "").strip(),
        )


class AutocatalogGarageCapacityListAPIView(APIView):
    def get(self, request):
        year_param = request.query_params.get("year")
        try:
            year = int(year_param) if year_param is not None else None
        except (TypeError, ValueError):
            year = None

        capacities = get_autocatalog_garage_capacities(
            make_id=request.query_params.get("make", "").strip(),
            model_id=request.query_params.get("model", "").strip(),
            year=year,
            modification=request.query_params.get("modification", "").strip(),
        )
        serializer = AutocatalogGarageCapacitySerializer([{"capacity": capacity} for capacity in capacities], many=True)
        return Response(serializer.data)
