from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbSyncState(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")
        PAUSED = "paused", _("Paused")

    source_table = models.CharField(_("Source table"), max_length=64, unique=True)
    status = models.CharField(_("Status"), max_length=32, choices=Status.choices, default=Status.PENDING)
    last_pk = models.BigIntegerField(_("Last PK"), null=True, blank=True)
    last_offset = models.BigIntegerField(_("Last offset"), null=True, blank=True)
    last_cursor = models.CharField(_("Last cursor"), max_length=255, blank=True, default="")
    total_rows = models.BigIntegerField(_("Total rows"), default=0)
    processed_rows = models.BigIntegerField(_("Processed rows"), default=0)
    failed_rows = models.BigIntegerField(_("Failed rows"), default=0)
    started_at = models.DateTimeField(_("Started at"), null=True, blank=True)
    finished_at = models.DateTimeField(_("Finished at"), null=True, blank=True)
    last_error = models.TextField(_("Last error"), blank=True, default="")
    metadata = models.JSONField(_("Metadata"), default=dict, blank=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        db_table = "autodb_pro_sync_state"
        verbose_name = _("Состояние синхронизации Auto_DB_Pro")
        verbose_name_plural = _("Состояния синхронизации Auto_DB_Pro")

    def __str__(self) -> str:
        return f"{self.source_table}:{self.status}"
