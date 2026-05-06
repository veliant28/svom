from django.urls import path

from apps.autodb.api.views import (
    AutoDbVehicleCatalogAPIView,
    AutoDbVehicleFilterOptionsAPIView,
    AutoDbPassangerCarAttributesAPIView,
    AutoDbPassangerCarDetailAPIView,
    AutoDbVehicleManufacturerModelsAPIView,
    AutoDbVehicleManufacturersAPIView,
    AutoDbVehicleModelPassangerCarsAPIView,
    AutoDbVehicleSearchAPIView,
)

app_name = "autodb_api"

urlpatterns = [
    path("vehicles/manufacturers/", AutoDbVehicleManufacturersAPIView.as_view(), name="vehicle-manufacturers"),
    path(
        "vehicles/manufacturers/<int:manufacturer_id>/models/",
        AutoDbVehicleManufacturerModelsAPIView.as_view(),
        name="vehicle-models-by-manufacturer",
    ),
    path(
        "vehicles/models/<int:model_id>/passanger-cars/",
        AutoDbVehicleModelPassangerCarsAPIView.as_view(),
        name="passanger-cars-by-model",
    ),
    path("vehicles/passanger-cars/<int:id>/", AutoDbPassangerCarDetailAPIView.as_view(), name="passanger-car-detail"),
    path(
        "vehicles/passanger-cars/<int:id>/attributes/",
        AutoDbPassangerCarAttributesAPIView.as_view(),
        name="passanger-car-attributes",
    ),
    path("vehicles/search/", AutoDbVehicleSearchAPIView.as_view(), name="vehicle-search"),
    path("vehicles/filter-options/", AutoDbVehicleFilterOptionsAPIView.as_view(), name="vehicle-filter-options"),
    path("vehicles/catalog/", AutoDbVehicleCatalogAPIView.as_view(), name="vehicle-catalog"),
]
