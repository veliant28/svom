from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import UUIDPrimaryKeyMixin


class SecurityEvent(UUIDPrimaryKeyMixin, models.Model):
    ACTOR_SYSTEM = "system"
    ACTOR_ADMIN = "admin"
    ACTOR_USER = "user"
    ACTOR_ANONYMOUS = "anonymous"
    ACTOR_TYPE_CHOICES = (
        (ACTOR_SYSTEM, _("System")),
        (ACTOR_ADMIN, _("Admin")),
        (ACTOR_USER, _("User")),
        (ACTOR_ANONYMOUS, _("Anonymous")),
    )

    created_at = models.DateTimeField(_("Created at"), auto_now_add=True, db_index=True)
    actor = models.ForeignKey("security.SecurityActor", on_delete=models.SET_NULL, blank=True, null=True, related_name="events")
    event_type = models.CharField(_("Event type"), max_length=64, db_index=True)
    severity = models.CharField(_("Severity"), max_length=16, blank=True, default="", db_index=True)
    source_ip = models.GenericIPAddressField(_("Source IP"), blank=True, null=True, db_index=True)
    source_kind = models.CharField(_("Source kind"), max_length=24, blank=True, default="")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="security_events")
    login_snapshot = models.CharField(_("Login snapshot"), max_length=255, blank=True, default="")
    email_snapshot = models.EmailField(_("Email snapshot"), blank=True, default="")
    method = models.CharField(_("Method"), max_length=16, blank=True, default="")
    endpoint = models.CharField(_("Endpoint"), max_length=512, blank=True, default="")
    status_code = models.PositiveSmallIntegerField(_("Status code"), blank=True, null=True)
    user_agent = models.TextField(_("User agent"), blank=True)
    fingerprint = models.CharField(_("Fingerprint"), max_length=255, blank=True, default="")
    session_key = models.CharField(_("Session key"), max_length=255, blank=True, default="")
    rule = models.CharField(_("Rule"), max_length=255, blank=True, default="")
    metadata = models.JSONField(_("Metadata"), blank=True, default=dict)
    actor_type = models.CharField(_("Actor type"), max_length=16, choices=ACTOR_TYPE_CHOICES, default=ACTOR_SYSTEM)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="security_events_as_actor",
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Security event")
        verbose_name_plural = _("Security events")
        indexes = [
            models.Index(fields=("actor", "created_at"), name="sec_event_actor_created_idx"),
            models.Index(fields=("event_type", "created_at"), name="sec_event_type_created_idx"),
            models.Index(fields=("source_ip", "created_at"), name="sec_event_ip_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.source_ip or self.actor_id}"
