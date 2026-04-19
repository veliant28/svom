from django.urls import path

from apps.users.api.views import (
    AuthLoginAPIView,
    AuthLogoutAPIView,
    CurrentUserAPIView,
    GarageVehicleListCreateAPIView,
    GarageVehicleRetrieveUpdateDestroyAPIView,
    PasswordChangeAPIView,
    ProfileUpdateAPIView,
)

app_name = "users_api"

urlpatterns = [
    path("auth/login/", AuthLoginAPIView.as_view(), name="auth-login"),
    path("auth/logout/", AuthLogoutAPIView.as_view(), name="auth-logout"),
    path("auth/current-user/", CurrentUserAPIView.as_view(), name="auth-current-user"),
    path("auth/profile/", ProfileUpdateAPIView.as_view(), name="auth-profile-update"),
    path("auth/change-password/", PasswordChangeAPIView.as_view(), name="auth-change-password"),
    path("garage-vehicles/", GarageVehicleListCreateAPIView.as_view(), name="garage-vehicles"),
    path("garage-vehicles/<uuid:id>/", GarageVehicleRetrieveUpdateDestroyAPIView.as_view(), name="garage-vehicle-detail"),
]
