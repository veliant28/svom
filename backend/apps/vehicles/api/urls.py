from django.urls import path

from apps.vehicles.api.views import (
    VehicleEngineListAPIView,
    VehicleGenerationListAPIView,
    VehicleMakeListAPIView,
    VehicleModelListAPIView,
    VehicleModificationListAPIView,
)

app_name = "vehicles_api"

urlpatterns = [
    path("makes/", VehicleMakeListAPIView.as_view(), name="make-list"),
    path("models/", VehicleModelListAPIView.as_view(), name="model-list"),
    path("generations/", VehicleGenerationListAPIView.as_view(), name="generation-list"),
    path("engines/", VehicleEngineListAPIView.as_view(), name="engine-list"),
    path("modifications/", VehicleModificationListAPIView.as_view(), name="modification-list"),
]
