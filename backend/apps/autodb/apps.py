from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class AutoDbConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.autodb"
    verbose_name = _("Auto_DB_Pro")

    def ready(self) -> None:
        super().ready()
        if bool(getattr(settings, "AUTODB_PRO_REMOTE_ENFORCE_GATEWAY_ONLY", True)):
            from apps.autodb.remote_access_guard import enforce_remote_db_gateway

            enforce_remote_db_gateway()
