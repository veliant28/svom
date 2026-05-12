from __future__ import annotations

from apps.autodb.models import AutoDbMatchJob, AutoDbMatchingRun
from apps.autodb.services.matching.clone_sync_planner import AutoDbCloneSyncPlanner
from apps.autodb.services.matching.enrichment_planner import AutoDbEnrichmentPlanner
from apps.autodb.services.matching.job_builder import AutoDbMatchJobBuilder
from apps.autodb.services.matching.link_audit_adapter import AutoDbLinkAuditAdapter
from apps.autodb.services.matching.local_lookup import AutoDbLocalLookupService
from apps.autodb.services.matching.remote_lookup import AutoDbRemoteLookupService
from apps.autodb.services.matching.safe_link_planner import AutoDbSafeLinkPlanner


class AutoDbMatchingPipelineService:
    """Stage-by-stage orchestrator. Apply stages require explicit command flags."""

    def __init__(
        self,
        *,
        job_builder: AutoDbMatchJobBuilder | None = None,
        local_lookup: AutoDbLocalLookupService | None = None,
        remote_lookup: AutoDbRemoteLookupService | None = None,
        clone_planner: AutoDbCloneSyncPlanner | None = None,
        link_audit: AutoDbLinkAuditAdapter | None = None,
        safe_link_planner: AutoDbSafeLinkPlanner | None = None,
        enrichment_planner: AutoDbEnrichmentPlanner | None = None,
    ):
        self.job_builder = job_builder or AutoDbMatchJobBuilder()
        self.local_lookup = local_lookup or AutoDbLocalLookupService()
        self.remote_lookup = remote_lookup or AutoDbRemoteLookupService()
        self.clone_planner = clone_planner or AutoDbCloneSyncPlanner()
        self.link_audit = link_audit or AutoDbLinkAuditAdapter()
        self.safe_link_planner = safe_link_planner or AutoDbSafeLinkPlanner()
        self.enrichment_planner = enrichment_planner or AutoDbEnrichmentPlanner()

    def build_jobs(self, *, run: AutoDbMatchingRun | None, supplier_code: str = "", limit: int = 100, dry_run: bool = True):
        return self.job_builder.build_jobs(run=run, supplier_code=supplier_code, limit=limit, dry_run=dry_run)

    def run_local(self, *, run: AutoDbMatchingRun | None, limit: int = 100, dry_run: bool = True):
        jobs = AutoDbMatchJob.objects.filter(status__in=[AutoDbMatchJob.STATUS_NEW, AutoDbMatchJob.STATUS_REMOTE_PENDING]).order_by(
            "priority", "created_at"
        )[: max(int(limit or 0), 1)]
        return [self.local_lookup.lookup_job(job, run=run, dry_run=dry_run) for job in jobs]

    def run_remote(self, *, run: AutoDbMatchingRun | None, limit: int = 300, dry_run: bool = True):
        rows = []
        jobs = AutoDbMatchJob.objects.filter(status=AutoDbMatchJob.STATUS_REMOTE_PENDING).order_by("priority", "created_at")[
            : max(int(limit or 0), 1)
        ]
        for job in jobs:
            result = self.remote_lookup.lookup_job(job, run=run, dry_run=dry_run)
            rows.append(result)
            if result.status == AutoDbMatchJob.STATUS_QUOTA_PAUSED:
                break
        return rows

    def plan_clone_sync(self, *, run: AutoDbMatchingRun | None, limit: int = 100, dry_run: bool = True):
        jobs = AutoDbMatchJob.objects.filter(
            status__in=[AutoDbMatchJob.STATUS_LOCAL_FOUND, AutoDbMatchJob.STATUS_REMOTE_FOUND, AutoDbMatchJob.STATUS_CLONE_SYNC_READY]
        ).order_by("priority", "created_at")[: max(int(limit or 0), 1)]
        return self.clone_planner.plan_jobs(jobs, run=run, dry_run=dry_run)

    def audit_links(self, *, run: AutoDbMatchingRun | None, limit: int = 100, dry_run: bool = True):
        jobs = AutoDbMatchJob.objects.filter(status__in=[AutoDbMatchJob.STATUS_LOCAL_FOUND, AutoDbMatchJob.STATUS_REMOTE_FOUND]).order_by(
            "priority", "created_at"
        )[: max(int(limit or 0), 1)]
        return [self.link_audit.audit_job(job, run=run, dry_run=dry_run) for job in jobs]

    def plan_safe_links(self, *, run: AutoDbMatchingRun | None, limit: int = 100, dry_run: bool = True):
        jobs = AutoDbMatchJob.objects.filter(status=AutoDbMatchJob.STATUS_SAFE_LINK_CANDIDATE).order_by("priority", "created_at")[
            : max(int(limit or 0), 1)
        ]
        return self.safe_link_planner.plan_jobs(jobs, run=run, dry_run=dry_run)

    def plan_enrichment(self, *, run: AutoDbMatchingRun | None, limit: int = 100, dry_run: bool = True):
        jobs = AutoDbMatchJob.objects.filter(status__in=[AutoDbMatchJob.STATUS_LINKED, AutoDbMatchJob.STATUS_SAFE_LINK_CANDIDATE]).order_by(
            "priority", "created_at"
        )[: max(int(limit or 0), 1)]
        return self.enrichment_planner.plan_jobs(jobs, run=run, dry_run=dry_run)
