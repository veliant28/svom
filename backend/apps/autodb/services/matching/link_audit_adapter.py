from __future__ import annotations

from dataclasses import dataclass

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob, AutoDbMatchingRun


@dataclass(frozen=True)
class AutoDbLinkAuditResult:
    job_id: str
    status: str
    classification: str
    supplier_id: int | None
    canonical_article: str
    remote_stored_article: str
    article_prd_present: bool
    prd_present: bool
    stock_qty: int | None
    search_modes: tuple[str, ...]
    reason: str


class AutoDbLinkAuditAdapter:
    deterministic_search_modes = ("deterministic_v3_canonical",)

    def audit_job(
        self,
        job: AutoDbMatchJob,
        *,
        run: AutoDbMatchingRun | None = None,
        dry_run: bool = True,
        stock_qty: int | None = None,
    ) -> AutoDbLinkAuditResult:
        evidence = self._latest_lookup_evidence(job)
        canonical = (evidence.canonical_article if evidence else "") or job.canonical_article
        remote_stored = (evidence.remote_stored_article if evidence else "") or canonical
        article_prd_present = bool(evidence.article_prd_present) if evidence else job.status == AutoDbMatchJob.STATUS_LOCAL_FOUND
        prd_present = bool(evidence.prd_present) if evidence else job.status == AutoDbMatchJob.STATUS_LOCAL_FOUND

        if job.status in {AutoDbMatchJob.STATUS_LOCAL_FOUND, AutoDbMatchJob.STATUS_REMOTE_FOUND} and article_prd_present and prd_present:
            classification = AutoDbMatchJob.STATUS_SAFE_LINK_CANDIDATE
            reason = "deterministic v3 canonical article has article_prd/prd linkage"
        else:
            classification = AutoDbMatchJob.STATUS_NEEDS_REVIEW
            reason = "deterministic v3 evidence is missing required linkage"

        if not dry_run:
            job.status = classification
            job.last_run = run
            job.last_error = "" if classification == AutoDbMatchJob.STATUS_SAFE_LINK_CANDIDATE else reason
            job.save(update_fields=["status", "last_run", "last_error", "updated_at"])
            AutoDbMatchEvidence.objects.create(
                job=job,
                stage="link_audit",
                source="deterministic_v3",
                result=classification,
                supplier_id=job.resolved_supplier_id,
                article_value=job.article_value,
                canonical_article=canonical,
                remote_stored_article=remote_stored,
                article_prd_present=article_prd_present,
                prd_present=prd_present,
                reason=reason,
                payload_json={
                    "stock_qty": stock_qty,
                    "stock_hard_gate": False,
                    "search_modes": list(self.deterministic_search_modes),
                    "fuzzy_oe_cross_name_disabled": True,
                },
            )

        return AutoDbLinkAuditResult(
            job_id=str(job.id),
            status=classification,
            classification=classification,
            supplier_id=job.resolved_supplier_id,
            canonical_article=canonical,
            remote_stored_article=remote_stored,
            article_prd_present=article_prd_present,
            prd_present=prd_present,
            stock_qty=stock_qty,
            search_modes=self.deterministic_search_modes,
            reason=reason,
        )

    def _latest_lookup_evidence(self, job: AutoDbMatchJob) -> AutoDbMatchEvidence | None:
        return (
            job.evidence.filter(stage__in=["local_lookup", "remote_lookup"])
            .order_by("-created_at")
            .first()
        )
