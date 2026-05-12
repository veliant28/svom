from __future__ import annotations

from dataclasses import dataclass

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob, AutoDbMatchingRun
from apps.catalog.models import ProductImage


@dataclass(frozen=True)
class AutoDbSafeLinkPlanRow:
    job_id: str
    product_id: str
    status: str
    action: str
    safe: bool
    no_name_overwrite: bool
    no_category_overwrite: bool
    no_photo_overwrite: bool
    no_price_stock_changes: bool
    reason: str


class AutoDbSafeLinkPlanner:
    def plan_job(
        self,
        job: AutoDbMatchJob,
        *,
        run: AutoDbMatchingRun | None = None,
        dry_run: bool = True,
    ) -> AutoDbSafeLinkPlanRow:
        del run
        image_count_before = ProductImage.objects.filter(product=job.product).count()
        safe = job.status == AutoDbMatchJob.STATUS_SAFE_LINK_CANDIDATE
        reason = "safe_link_candidate can be applied by a later guarded linker" if safe else f"status {job.status} is not apply-safe"
        row = AutoDbSafeLinkPlanRow(
            job_id=str(job.id),
            product_id=str(job.product_id),
            status=job.status,
            action="plan_safe_link" if safe else "skip",
            safe=safe,
            no_name_overwrite=True,
            no_category_overwrite=True,
            no_photo_overwrite=ProductImage.objects.filter(product=job.product).count() == image_count_before,
            no_price_stock_changes=True,
            reason=reason,
        )
        if not dry_run:
            AutoDbMatchEvidence.objects.create(
                job=job,
                stage="safe_link_plan",
                source="planner",
                result="safe" if safe else "skipped",
                supplier_id=job.resolved_supplier_id,
                article_value=job.article_value,
                canonical_article=job.canonical_article,
                reason=reason,
                payload_json={
                    "no_product_name_overwrite": True,
                    "no_category_overwrite": True,
                    "no_photo_overwrite": True,
                    "no_price_stock_changes": True,
                    "foundation_apply_writes_product": False,
                },
            )
        return row

    def plan_jobs(
        self,
        jobs,
        *,
        run: AutoDbMatchingRun | None = None,
        dry_run: bool = True,
    ) -> list[AutoDbSafeLinkPlanRow]:
        return [self.plan_job(job, run=run, dry_run=dry_run) for job in jobs]

    def apply_job(self, job: AutoDbMatchJob, *, apply: bool = False) -> AutoDbSafeLinkPlanRow:
        if not apply:
            raise ValueError("--apply is required for safe link apply")
        # Foundation phase deliberately does not write Product link fields.
        return self.plan_job(job, dry_run=False)
