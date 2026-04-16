from django.urls import path

from apps.autocatalog.api.views import (
    AutocatalogGarageCapacityListAPIView,
    AutocatalogGarageEngineListAPIView,
    AutocatalogGarageMakeListAPIView,
    AutocatalogGarageModelListAPIView,
    AutocatalogGarageModificationListAPIView,
    AutocatalogGarageYearListAPIView,
)

app_name = "autocatalog_api"

urlpatterns = [
    path("garage/makes/", AutocatalogGarageMakeListAPIView.as_view(), name="garage-makes"),
    path("garage/models/", AutocatalogGarageModelListAPIView.as_view(), name="garage-models"),
    path("garage/years/", AutocatalogGarageYearListAPIView.as_view(), name="garage-years"),
    path("garage/modifications/", AutocatalogGarageModificationListAPIView.as_view(), name="garage-modifications"),
    path("garage/capacities/", AutocatalogGarageCapacityListAPIView.as_view(), name="garage-capacities"),
    path("garage/engines/", AutocatalogGarageEngineListAPIView.as_view(), name="garage-engines"),
]
