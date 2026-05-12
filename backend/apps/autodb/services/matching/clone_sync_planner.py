from __future__ import annotations

from dataclasses import dataclass

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob, AutoDbMatchingRun
from apps.autodb.services.matching.constants import CLONE_SYNC_TABLES, DISABLED_TABLES, IMAGES_DISABLED_REASON


@dataclass(frozen=True)
class AutoDbCloneSyncPlanRow:
    job_id: str
    supplier_id: int | None
    canonical_article: str
    table: str
    action: str
    reason: str


class AutoDbCloneSyncPlanner:
    sync_tables = CLONE_SYNC_TABLES
    disabled_tables = DISABLED_TABLES

    def plan_job(
        self,
        job: AutoDbMatchJob,
        *,
        run: AutoDbMatchingRun | None = None,
        dry_run: bool = True,
    ) -> list[AutoDbCloneSyncPlanRow]:
        rows: list[AutoDbCloneSyncPlanRow] = []
        if job.status not in {AutoDbMatchJob.STATUS_REMOTE_FOUND, AutoDbMatchJob.STATUS_LOCAL_FOUND, AutoDbMatchJob.STATUS_CLONE_SYNC_READY}:
            rows.append(self._row(job, table="", action="skip", reason=f"status {job.status} is not clone-sync ready"))
            return rows
        for table in self.sync_tables:
            rows.append(self._row(job, table=table, action="plan_sync", reason="source-aware deterministic article candidate"))
        rows.append(self._row(job, table="article_images", action="disabled", reason=IMAGES_DISABLED_REASON))

        if not dry_run:
            job.status = AutoDbMatchJob.STATUS_CLONE_SYNC_READY
            job.last_run = run
            job.save(update_fields=["status", "last_run", "updated_at"])
            AutoDbMatchEvidence.objects.create(
                job=job,
                stage="clone_sync_plan",
                source="planner",
                result=AutoDbMatchJob.STATUS_CLONE_SYNC_READY,
                supplier_id=job.resolved_supplier_id,
                article_value=job.article_value,
                canonical_article=job.canonical_article,
                reason="clone sync plan ready; article_images excluded",
                payload_json={"tables": list(self.sync_tables), "disabled_tables": list(self.disabled_tables)},
            )
        return rows

    def plan_jobs(
        self,
        jobs,
        *,
        run: AutoDbMatchingRun | None = None,
        dry_run: bool = True,
    ) -> list[AutoDbCloneSyncPlanRow]:
        rows: list[AutoDbCloneSyncPlanRow] = []
        for job in jobs:
            rows.extend(self.plan_job(job, run=run, dry_run=dry_run))
        return rows

    def _row(self, job: AutoDbMatchJob, *, table: str, action: str, reason: str) -> AutoDbCloneSyncPlanRow:
        return AutoDbCloneSyncPlanRow(
            job_id=str(job.id),
            supplier_id=job.resolved_supplier_id,
            canonical_article=job.canonical_article,
            table=table,
            action=action,
            reason=reason,
        )
