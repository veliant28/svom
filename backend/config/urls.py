from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path("api/backoffice/", include("apps.backoffice.api.urls")),
    path("api/autocatalog/", include("apps.autocatalog.api.urls")),
    path("api/core/", include("apps.core.api.urls")),
    path("api/catalog/", include("apps.catalog.api.urls")),
    path("api/marketing/", include("apps.marketing.api.urls")),
    path("api/vehicles/", include("apps.vehicles.api.urls")),
    path("api/users/", include("apps.users.api.urls")),
    path("api/commerce/", include("apps.commerce.api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
