from importlib import import_module

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SupplierImportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.supplier_imports"
    verbose_name = _("Импорт поставщиков")

    def ready(self) -> None:
        import_module("apps.supplier_imports.tasks")
