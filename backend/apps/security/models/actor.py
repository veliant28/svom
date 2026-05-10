from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class SecurityActor(UUIDPrimaryKeyMixin, TimestampedMixin):
    SOURCE_IPV4 = "ipv4"
    SOURCE_IPV6 = "ipv6"
    SOURCE_UNKNOWN = "unknown"
    SOURCE_CHOICES = (
        (SOURCE_IPV4, _("IPv4")),
        (SOURCE_IPV6, _("IPv6")),
        (SOURCE_UNKNOWN, _("Unknown")),
    )

    THREAT_LOW = "low"
    THREAT_MEDIUM = "medium"
    THREAT_HIGH = "high"
    THREAT_CRITICAL = "critical"
    THREAT_CHOICES = (
        (THREAT_LOW, _("Low")),
        (THREAT_MEDIUM, _("Medium")),
        (THREAT_HIGH, _("High")),
        (THREAT_CRITICAL, _("Critical")),
    )

    STATUS_SUSPICIOUS = "suspicious"
    STATUS_BLOCKED = "blocked"
    STATUS_WHITELISTED = "whitelisted"
    STATUS_UNBLOCKED = "unblocked"
    STATUS_EXPIRED = "expired"
    STATUS_ERROR = "error"
    STATUS_CHOICES = (
        (STATUS_SUSPICIOUS, _("Suspicious")),
        (STATUS_BLOCKED, _("Blocked")),
        (STATUS_WHITELISTED, _("Whitelisted")),
        (STATUS_UNBLOCKED, _("Unblocked")),
        (STATUS_EXPIRED, _("Expired")),
        (STATUS_ERROR, _("Error")),
    )

    source_ip = models.GenericIPAddressField(_("Source IP"), blank=True, null=True, db_index=True)
    source_identifier = models.CharField(_("Source identifier"), max_length=255, db_index=True)
    source_kind = models.CharField(_("Source kind"), max_length=24, choices=SOURCE_CHOICES, default=SOURCE_UNKNOWN)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="security_actors",
        verbose_name=_("User"),
    )
    login_snapshot = models.CharField(_("Login snapshot"), max_length=255, blank=True, default="")
    email_snapshot = models.EmailField(_("Email snapshot"), blank=True, default="")
    threat_level = models.CharField(_("Threat level"), max_length=16, choices=THREAT_CHOICES, default=THREAT_LOW, db_index=True)
    threat_score = models.PositiveSmallIntegerField(_("Threat score"), blank=True, null=True)
    status = models.CharField(_("Status"), max_length=24, choices=STATUS_CHOICES, default=STATUS_SUSPICIOUS, db_index=True)
    block_count = models.PositiveIntegerField(_("Block count"), default=0)
    first_seen_at = models.DateTimeField(_("First seen at"), blank=True, null=True)
    last_seen_at = models.DateTimeField(_("Last seen at"), blank=True, null=True)
    last_blocked_at = models.DateTimeField(_("Last blocked at"), blank=True, null=True)
    last_unblocked_at = models.DateTimeField(_("Last unblocked at"), blank=True, null=True)
    metadata = models.JSONField(_("Metadata"), blank=True, default=dict)

    class Meta:
        ordering = ("-last_seen_at", "-updated_at")
        verbose_name = _("Security actor")
        verbose_name_plural = _("Security actors")
        constraints = [
            models.UniqueConstraint(fields=("source_identifier",), name="security_actor_source_identifier_uniq"),
        ]
        indexes = [
            models.Index(fields=("status", "threat_level"), name="sec_actor_status_threat_idx"),
            models.Index(fields=("last_seen_at",), name="sec_actor_last_seen_idx"),
        ]

    def __str__(self) -> str:
        return self.source_identifier
