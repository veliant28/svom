from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import UUIDPrimaryKeyMixin


class SecurityAuditLog(UUIDPrimaryKeyMixin, models.Model):
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True, db_index=True)
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="security_audit_logs",
        verbose_name=_("Admin user"),
    )
    action = models.CharField(_("Action"), max_length=64, db_index=True)
    target_type = models.CharField(_("Target type"), max_length=64, db_index=True)
    target_id = models.CharField(_("Target ID"), max_length=64, blank=True, default="")
    target_label = models.CharField(_("Target label"), max_length=255, blank=True, default="")
    old_value = models.JSONField(_("Old value"), blank=True, null=True)
    new_value = models.JSONField(_("New value"), blank=True, null=True)
    ip = models.GenericIPAddressField(_("IP"), blank=True, null=True)
    user_agent = models.TextField(_("User agent"), blank=True)
    comment = models.TextField(_("Comment"), blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Security audit log")
        verbose_name_plural = _("Security audit logs")
        indexes = [
            models.Index(fields=("target_type", "target_id"), name="sec_audit_target_idx"),
            models.Index(fields=("action", "created_at"), name="sec_audit_action_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action}:{self.target_label or self.target_id}"
