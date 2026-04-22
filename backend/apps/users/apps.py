from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = _("Пользователи")

    def ready(self):
        # Register users domain signals.
        from . import signals  # noqa: F401
