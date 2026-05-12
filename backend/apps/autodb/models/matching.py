from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class AutoDbMatchingRun(UUIDPrimaryKeyMixin, TimestampedMixin):
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_PARTIAL = "partial"
    STATUS_CHOICES = (
        (STATUS_RUNNING, "running"),
        (STATUS_SUCCESS, "success"),
        (STATUS_FAILED, "failed"),
        (STATUS_PARTIAL, "partial"),
    )

    run_type = models.CharField(_("Run type"), max_length=64, db_index=True)
    status = models.CharField(_("Status"), max_length=24, choices=STATUS_CHOICES, default=STATUS_RUNNING, db_index=True)
    started_at = models.DateTimeField(_("Started at"), blank=True, null=True)
    finished_at = models.DateTimeField(_("Finished at"), blank=True, null=True)
    dry_run = models.BooleanField(_("Dry run"), default=True, db_index=True)
    created_by_source = models.CharField(_("Created by/source"), max_length=128, blank=True, default="")
    summary_json = models.JSONField(_("Summary"), default=dict, blank=True)
    error = models.TextField(_("Error"), blank=True, default="")

    class Meta:
        db_table = "autodb_matching_runs"
        ordering = ("-created_at",)
        verbose_name = _("Auto_DB matching run")
        verbose_name_plural = _("Auto_DB matching runs")
        indexes = [
            models.Index(fields=("run_type", "status"), name="autodb_match_run_type_stat_idx"),
            models.Index(fields=("-created_at",), name="autodb_match_run_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.run_type}:{self.status}:{self.id}"


class AutoDbMatchJob(UUIDPrimaryKeyMixin, TimestampedMixin):
    STATUS_NEW = "new"
    STATUS_SKIPPED_NON_TECDOC = "skipped_non_tecdoc"
    STATUS_SKIPPED_BRAND_UNRESOLVED = "skipped_brand_unresolved"
    STATUS_SKIPPED_SPLIT_NEEDED = "skipped_split_needed"
    STATUS_SKIPPED_UNSAFE_AMBIGUOUS = "skipped_unsafe_ambiguous"
    STATUS_SKIPPED_BAD_ARTICLE_SOURCE = "skipped_bad_article_source"
    STATUS_LOCAL_FOUND = "local_found"
    STATUS_REMOTE_PENDING = "remote_pending"
    STATUS_REMOTE_FOUND = "remote_found"
    STATUS_REMOTE_NOT_FOUND = "remote_not_found"
    STATUS_QUOTA_PAUSED = "quota_paused"
    STATUS_CLONE_SYNC_READY = "clone_sync_ready"
    STATUS_CLONE_SYNCED = "clone_synced"
    STATUS_SAFE_LINK_CANDIDATE = "safe_link_candidate"
    STATUS_LINKED = "linked"
    STATUS_NEEDS_REVIEW = "needs_review"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_NEW, "new"),
        (STATUS_SKIPPED_NON_TECDOC, "skipped_non_tecdoc"),
        (STATUS_SKIPPED_BRAND_UNRESOLVED, "skipped_brand_unresolved"),
        (STATUS_SKIPPED_SPLIT_NEEDED, "skipped_split_needed"),
        (STATUS_SKIPPED_UNSAFE_AMBIGUOUS, "skipped_unsafe_ambiguous"),
        (STATUS_SKIPPED_BAD_ARTICLE_SOURCE, "skipped_bad_article_source"),
        (STATUS_LOCAL_FOUND, "local_found"),
        (STATUS_REMOTE_PENDING, "remote_pending"),
        (STATUS_REMOTE_FOUND, "remote_found"),
        (STATUS_REMOTE_NOT_FOUND, "remote_not_found"),
        (STATUS_QUOTA_PAUSED, "quota_paused"),
        (STATUS_CLONE_SYNC_READY, "clone_sync_ready"),
        (STATUS_CLONE_SYNCED, "clone_synced"),
        (STATUS_SAFE_LINK_CANDIDATE, "safe_link_candidate"),
        (STATUS_LINKED, "linked"),
        (STATUS_NEEDS_REVIEW, "needs_review"),
        (STATUS_REJECTED, "rejected"),
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="autodb_match_jobs",
        verbose_name=_("Product"),
    )
    supplier_offer = models.ForeignKey(
        "pricing.SupplierOffer",
        on_delete=models.SET_NULL,
        related_name="autodb_match_jobs",
        verbose_name=_("Supplier offer"),
        blank=True,
        null=True,
    )
    supplier_code = models.CharField(_("Supplier code"), max_length=64, blank=True, default="", db_index=True)
    raw_brand = models.CharField(_("Raw brand"), max_length=255, blank=True, default="")
    normalized_brand = models.CharField(_("Normalized brand"), max_length=255, blank=True, default="", db_index=True)
    resolved_supplier_id = models.BigIntegerField(_("Auto_DB supplier ID"), blank=True, null=True, db_index=True)
    article_source_type = models.CharField(_("Article source type"), max_length=64, blank=True, default="", db_index=True)
    article_value = models.CharField(_("Article value"), max_length=128, blank=True, default="")
    canonical_article = models.CharField(_("Canonical article"), max_length=128, blank=True, default="", db_index=True)
    status = models.CharField(_("Status"), max_length=48, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)
    priority = models.PositiveSmallIntegerField(_("Priority"), default=100, db_index=True)
    attempt_count = models.PositiveIntegerField(_("Attempt count"), default=0)
    last_error = models.TextField(_("Last error"), blank=True, default="")
    next_retry_at = models.DateTimeField(_("Next retry at"), blank=True, null=True, db_index=True)
    last_run = models.ForeignKey(
        "autodb.AutoDbMatchingRun",
        on_delete=models.SET_NULL,
        related_name="jobs",
        verbose_name=_("Last run"),
        blank=True,
        null=True,
    )
    metadata_json = models.JSONField(_("Metadata"), default=dict, blank=True)

    class Meta:
        db_table = "autodb_match_jobs"
        ordering = ("priority", "-created_at")
        verbose_name = _("Auto_DB match job")
        verbose_name_plural = _("Auto_DB match jobs")
        indexes = [
            models.Index(fields=("status", "priority"), name="autodb_match_job_status_pr_idx"),
            models.Index(fields=("supplier_code", "status"), name="autodb_match_job_sup_stat_idx"),
            models.Index(fields=("resolved_supplier_id", "canonical_article"), name="autodb_match_job_supp_art_idx"),
            models.Index(fields=("product", "status"), name="autodb_match_job_prod_stat_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.product_id}:{self.resolved_supplier_id or '-'}:{self.canonical_article or '-'}:{self.status}"


class AutoDbMatchEvidence(UUIDPrimaryKeyMixin, TimestampedMixin):
    job = models.ForeignKey(
        "autodb.AutoDbMatchJob",
        on_delete=models.CASCADE,
        related_name="evidence",
        verbose_name=_("Job"),
    )
    stage = models.CharField(_("Stage"), max_length=64, db_index=True)
    source = models.CharField(_("Source"), max_length=64, blank=True, default="", db_index=True)
    result = models.CharField(_("Result"), max_length=64, blank=True, default="", db_index=True)
    supplier_id = models.BigIntegerField(_("Auto_DB supplier ID"), blank=True, null=True, db_index=True)
    article_value = models.CharField(_("Article value"), max_length=128, blank=True, default="")
    canonical_article = models.CharField(_("Canonical article"), max_length=128, blank=True, default="", db_index=True)
    remote_stored_article = models.CharField(_("Remote stored article"), max_length=128, blank=True, default="")
    article_prd_present = models.BooleanField(_("article_prd present"), default=False)
    prd_present = models.BooleanField(_("prd present"), default=False)
    reason = models.TextField(_("Reason"), blank=True, default="")
    payload_json = models.JSONField(_("Payload"), default=dict, blank=True)

    class Meta:
        db_table = "autodb_match_evidence"
        ordering = ("-created_at",)
        verbose_name = _("Auto_DB match evidence")
        verbose_name_plural = _("Auto_DB match evidence")
        indexes = [
            models.Index(fields=("job", "stage"), name="autodb_match_ev_job_stage_idx"),
            models.Index(fields=("stage", "result"), name="autodb_match_ev_stage_res_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.job_id}:{self.stage}:{self.result}"


class AutoDbRemoteQuotaState(UUIDPrimaryKeyMixin, TimestampedMixin):
    remote_key = models.CharField(_("Remote key"), max_length=128, unique=True)
    estimated_limit_per_hour = models.PositiveIntegerField(_("Estimated limit per hour"), default=10000)
    window_started_at = models.DateTimeField(_("Window started at"), blank=True, null=True)
    expected_reset_at = models.DateTimeField(_("Expected reset at"), blank=True, null=True)
    last_ok_at = models.DateTimeField(_("Last OK at"), blank=True, null=True)
    last_query_at = models.DateTimeField(_("Last query at"), blank=True, null=True)
    last_quota_error_at = models.DateTimeField(_("Last quota error at"), blank=True, null=True)
    estimated_queries_used = models.PositiveIntegerField(_("Estimated queries used"), default=0)
    cooldown_until = models.DateTimeField(_("Cooldown until"), blank=True, null=True, db_index=True)
    recent_points_json = models.JSONField(_("Recent quota points"), default=list, blank=True)
    last_error = models.TextField(_("Last error"), blank=True, default="")

    class Meta:
        db_table = "autodb_remote_quota_states"
        ordering = ("remote_key",)
        verbose_name = _("Auto_DB remote quota state")
        verbose_name_plural = _("Auto_DB remote quota states")
        indexes = [
            models.Index(fields=("remote_key", "cooldown_until"), name="autodb_quota_key_cool_idx"),
        ]

    def __str__(self) -> str:
        return self.remote_key
