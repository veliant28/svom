from django.urls import path

from .views.health import HealthCheckView

app_name = "core_api"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
]
