from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import UUIDPrimaryKeyMixin


class SecurityBlock(UUIDPrimaryKeyMixin, models.Model):
    TYPE_IP = "ip"
    TYPE_ACCOUNT = "account"
    TYPE_USER_AGENT = "user_agent"
    TYPE_FINGERPRINT = "fingerprint"
    TYPE_SUBNET = "subnet"
    TYPE_CHOICES = (
        (TYPE_IP, _("IP")),
        (TYPE_ACCOUNT, _("Account")),
        (TYPE_USER_AGENT, _("User agent")),
        (TYPE_FINGERPRINT, _("Fingerprint")),
        (TYPE_SUBNET, _("Subnet")),
    )

    STATUS_ACTIVE = "active"
    STATUS_RELEASED = "released"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, _("Active")),
        (STATUS_RELEASED, _("Released")),
        (STATUS_EXPIRED, _("Expired")),
    )

    actor = models.ForeignKey("security.SecurityActor", on_delete=models.CASCADE, related_name="blocks", verbose_name=_("Actor"))
    block_type = models.CharField(_("Block type"), max_length=24, choices=TYPE_CHOICES, default=TYPE_IP)
    value = models.CharField(_("Value"), max_length=255, db_index=True)
    status = models.CharField(_("Status"), max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    reason = models.TextField(_("Reason"), blank=True)
    comment = models.TextField(_("Comment"), blank=True)
    is_automatic = models.BooleanField(_("Automatic"), default=True)
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="security_blocks_created",
        verbose_name=_("Blocked by"),
    )
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="security_blocks_released",
        verbose_name=_("Released by"),
    )
    blocked_at = models.DateTimeField(_("Blocked at"))
    expires_at = models.DateTimeField(_("Expires at"), blank=True, null=True)
    released_at = models.DateTimeField(_("Released at"), blank=True, null=True)
    release_reason = models.TextField(_("Release reason"), blank=True)
    metadata = models.JSONField(_("Metadata"), blank=True, default=dict)

    class Meta:
        ordering = ("-blocked_at",)
        verbose_name = _("Security block")
        verbose_name_plural = _("Security blocks")
        indexes = [
            models.Index(fields=("actor", "status"), name="sec_block_actor_status_idx"),
            models.Index(fields=("status", "expires_at"), name="sec_block_status_expires_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.value}:{self.status}"
