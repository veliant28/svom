from __future__ import annotations

from dataclasses import dataclass

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob, AutoDbMatchingRun
from apps.autodb.services.matching.constants import IMAGES_DISABLED_REASON


@dataclass(frozen=True)
class AutoDbEnrichmentPlanRow:
    job_id: str
    product_id: str
    enrichment_type: str
    action: str
    reason: str


class AutoDbEnrichmentPlanner:
    enabled_types = ("attributes", "fitments")
    disabled_types = ("images",)

    def plan_job(
        self,
        job: AutoDbMatchJob,
        *,
        run: AutoDbMatchingRun | None = None,
        dry_run: bool = True,
    ) -> list[AutoDbEnrichmentPlanRow]:
        rows = [
            AutoDbEnrichmentPlanRow(str(job.id), str(job.product_id), "attributes", "plan_enrichment", "attributes only"),
            AutoDbEnrichmentPlanRow(str(job.id), str(job.product_id), "fitments", "plan_enrichment", "fitments only"),
            AutoDbEnrichmentPlanRow(str(job.id), str(job.product_id), "images", "disabled", IMAGES_DISABLED_REASON),
        ]
        if not dry_run:
            AutoDbMatchEvidence.objects.create(
                job=job,
                stage="enrichment_plan",
                source="planner",
                result="planned",
                supplier_id=job.resolved_supplier_id,
                article_value=job.article_value,
                canonical_article=job.canonical_article,
                reason="attributes/fitments only; images disabled",
                payload_json={"enabled": list(self.enabled_types), "disabled": list(self.disabled_types)},
            )
            job.last_run = run
            job.save(update_fields=["last_run", "updated_at"])
        return rows

    def plan_jobs(
        self,
        jobs,
        *,
        run: AutoDbMatchingRun | None = None,
        dry_run: bool = True,
    ) -> list[AutoDbEnrichmentPlanRow]:
        rows: list[AutoDbEnrichmentPlanRow] = []
        for job in jobs:
            rows.extend(self.plan_job(job, run=run, dry_run=dry_run))
        return rows

    def apply_attributes(self, jobs, *, apply: bool = False) -> list[AutoDbEnrichmentPlanRow]:
        if not apply:
            raise ValueError("--apply is required for attributes apply")
        return [
            AutoDbEnrichmentPlanRow(str(job.id), str(job.product_id), "attributes", "apply_blocked_foundation", "foundation does not apply enrichment")
            for job in jobs
        ]

    def apply_fitments(self, jobs, *, apply: bool = False) -> list[AutoDbEnrichmentPlanRow]:
        if not apply:
            raise ValueError("--apply is required for fitments apply")
        return [
            AutoDbEnrichmentPlanRow(str(job.id), str(job.product_id), "fitments", "apply_blocked_foundation", "foundation does not apply enrichment")
            for job in jobs
        ]
