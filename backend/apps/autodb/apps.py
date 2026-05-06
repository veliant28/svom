from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AutoDbConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.autodb"
    verbose_name = _("Auto_DB_Pro")
