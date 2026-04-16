from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AutocatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.autocatalog"
    verbose_name = _("Автокаталог")
