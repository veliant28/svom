from importlib import import_module

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PricingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pricing"
    verbose_name = _("Ценообразование")

    def ready(self) -> None:
        import_module("apps.pricing.tasks")
