from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CompatibilityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.compatibility"
    verbose_name = _("Совместимость")
