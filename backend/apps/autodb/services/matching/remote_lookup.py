from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob, AutoDbMatchingRun, AutoDbRemoteQuotaState
from apps.autodb.services.lookup_v3_readonly import AutoDbLookupV3ReadOnlyService
from apps.autodb.services.matching.constants import REMOTE_QUOTA_KEY
from apps.autodb.services.matching.quota_tracker import AutoDbRemoteQuotaTracker
from apps.autodb.services.remote_client import AutoDbProRemoteClientError


@dataclass(frozen=True)
class AutoDbRemoteLookupResult:
    job_id: str
    status: str
    supplier_id: int | None
    canonical_article: str
    remote_stored_article: str
    remote_queries: int
    reason: str
    matched_source: str = ""


class AutoDbRemoteLookupService:
    def __init__(
        self,
        *,
        lookup_service: AutoDbLookupV3ReadOnlyService | None = None,
        remote_key: str = REMOTE_QUOTA_KEY,
        cooldown_minutes: int = 60,
        quota_tracker: AutoDbRemoteQuotaTracker | None = None,
    ):
        self.lookup_service = lookup_service or AutoDbLookupV3ReadOnlyService()
        self.remote_key = remote_key
        self.cooldown_minutes = int(cooldown_minutes)
        self.quota_tracker = quota_tracker or AutoDbRemoteQuotaTracker()
        self._cache: dict[tuple[str, str], Any] = {}

    def lookup_job(
        self,
        job: AutoDbMatchJob,
        *,
        run: AutoDbMatchingRun | None = None,
        dry_run: bool = True,
    ) -> AutoDbRemoteLookupResult:
        del dry_run
        quota = self._quota_state()
        now = timezone.now()
        if quota.cooldown_until and quota.cooldown_until > now:
            return self._quota_paused(job=job, run=run, quota=quota, error="remote quota cooldown active")

        try:
            self._check_connection()
        except Exception as exc:  # noqa: BLE001
            if self._is_quota_error(exc):
                return self._quota_paused(job=job, run=run, quota=quota, error=str(exc))
            return self._finish(
                job=job,
                run=run,
                status=AutoDbMatchJob.STATUS_REMOTE_NOT_FOUND,
                supplier_id=job.resolved_supplier_id,
                canonical_article=job.canonical_article,
                remote_stored_article="",
                remote_queries=0,
                matched_source="",
                reason=f"remote precheck failed: {exc}",
                payload={"precheck": "SELECT 1"},
            )

        cache_key = (str(job.resolved_supplier_id or job.raw_brand), str(job.canonical_article or ""))
        try:
            if cache_key not in self._cache:
                self._cache[cache_key] = self.lookup_service.lookup(brand=job.raw_brand, article=job.canonical_article)
            result = self._cache[cache_key]
        except Exception as exc:  # noqa: BLE001
            if self._is_quota_error(exc):
                return self._quota_paused(job=job, run=run, quota=quota, error=str(exc))
            return self._finish(
                job=job,
                run=run,
                status=AutoDbMatchJob.STATUS_REMOTE_NOT_FOUND,
                supplier_id=job.resolved_supplier_id,
                canonical_article=job.canonical_article,
                remote_stored_article="",
                remote_queries=0,
                matched_source="",
                reason=str(exc),
                payload={"exception": exc.__class__.__name__},
            )

        if self._is_quota_error(getattr(result, "error", "")):
            return self._quota_paused(job=job, run=run, quota=quota, error=str(getattr(result, "error", "")))

        remote_queries = int(getattr(result, "remote_queries", 0) or 0)
        self.quota_tracker.record_success(
            quota,
            query_count=remote_queries + 1,
            run_id=str(run.id) if run else "",
            status="ok",
        )

        status = AutoDbMatchJob.STATUS_REMOTE_FOUND if bool(getattr(result, "found", False)) else AutoDbMatchJob.STATUS_REMOTE_NOT_FOUND
        reason = "remote deterministic lookup found article" if status == AutoDbMatchJob.STATUS_REMOTE_FOUND else "remote deterministic lookup missed"
        return self._finish(
            job=job,
            run=run,
            status=status,
            supplier_id=getattr(result, "supplier_id", None) or job.resolved_supplier_id,
            canonical_article=getattr(result, "canonical_article", "") or job.canonical_article,
            remote_stored_article=getattr(result, "remote_stored_article", "") or "",
            remote_queries=remote_queries,
            matched_source=getattr(result, "matched_source", "") or "",
            reason=reason,
            payload={
                "matched_table": getattr(result, "matched_table", ""),
                "local_hits": getattr(result, "local_hits", 0),
                "remote_hits": getattr(result, "remote_hits", 0),
                "article_prd_rows": getattr(result, "article_prd_rows", 0),
                "prd_rows": getattr(result, "prd_rows", 0),
                "linkage_present": bool(getattr(result, "linkage_present", False)),
                "path": getattr(result, "path", ""),
            },
        )

    def _finish(
        self,
        *,
        job: AutoDbMatchJob,
        run: AutoDbMatchingRun | None,
        status: str,
        supplier_id: int | None,
        canonical_article: str,
        remote_stored_article: str,
        remote_queries: int,
        matched_source: str,
        reason: str,
        payload: dict[str, Any],
    ) -> AutoDbRemoteLookupResult:
        job.status = status
        job.last_run = run
        job.attempt_count += 1
        job.last_error = "" if status == AutoDbMatchJob.STATUS_REMOTE_FOUND else reason
        job.save(update_fields=["status", "last_run", "attempt_count", "last_error", "updated_at"])
        AutoDbMatchEvidence.objects.create(
            job=job,
            stage="remote_lookup",
            source="lookup_v3_readonly",
            result=status,
            supplier_id=supplier_id,
            article_value=job.article_value,
            canonical_article=canonical_article,
            remote_stored_article=remote_stored_article,
            article_prd_present=int(payload.get("article_prd_rows") or 0) > 0,
            prd_present=int(payload.get("prd_rows") or 0) > 0,
            reason=reason,
            payload_json={**payload, "remote_queries": remote_queries, "matched_source": matched_source},
        )
        return AutoDbRemoteLookupResult(
            job_id=str(job.id),
            status=status,
            supplier_id=supplier_id,
            canonical_article=canonical_article,
            remote_stored_article=remote_stored_article,
            remote_queries=remote_queries,
            reason=reason,
            matched_source=matched_source,
        )

    def _quota_paused(
        self,
        *,
        job: AutoDbMatchJob,
        run: AutoDbMatchingRun | None,
        quota: AutoDbRemoteQuotaState,
        error: str,
    ) -> AutoDbRemoteLookupResult:
        self.quota_tracker.record_quota_error(
            quota,
            error=error,
            cooldown_minutes=self.cooldown_minutes,
            run_id=str(run.id) if run else "",
        )
        job.status = AutoDbMatchJob.STATUS_QUOTA_PAUSED
        job.last_run = run
        job.last_error = error
        job.next_retry_at = quota.cooldown_until
        job.save(update_fields=["status", "last_run", "last_error", "next_retry_at", "updated_at"])
        AutoDbMatchEvidence.objects.create(
            job=job,
            stage="remote_lookup",
            source="lookup_v3_readonly",
            result=AutoDbMatchJob.STATUS_QUOTA_PAUSED,
            supplier_id=job.resolved_supplier_id,
            article_value=job.article_value,
            canonical_article=job.canonical_article,
            reason=error,
            payload_json={"quota_key": self.remote_key, "cooldown_until": quota.cooldown_until.isoformat()},
        )
        return AutoDbRemoteLookupResult(
            job_id=str(job.id),
            status=AutoDbMatchJob.STATUS_QUOTA_PAUSED,
            supplier_id=job.resolved_supplier_id,
            canonical_article=job.canonical_article,
            remote_stored_article="",
            remote_queries=0,
            reason=error,
        )

    def _quota_state(self) -> AutoDbRemoteQuotaState:
        quota, _created = AutoDbRemoteQuotaState.objects.get_or_create(remote_key=self.remote_key)
        return quota

    def _check_connection(self) -> None:
        client = getattr(getattr(self.lookup_service, "storage", None), "remote_client", None)
        if client is None:
            return
        ok = client.check_connection()
        if not ok:
            raise AutoDbProRemoteClientError("Auto_DB remote SELECT 1 precheck returned false")

    def _is_quota_error(self, value: object) -> bool:
        text = str(value or "").lower()
        return "error 1226" in text or "max_questions" in text or "quota" in text
