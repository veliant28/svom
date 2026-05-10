from django.urls import path

from .views.health import HealthCheckView, SecurityBlockedInfoView

app_name = "core_api"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("security-blocked-info/", SecurityBlockedInfoView.as_view(), name="security-blocked-info"),
]
