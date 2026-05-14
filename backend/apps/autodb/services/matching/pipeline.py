from __future__ import annotations

from dataclasses import dataclass

from apps.autodb.models import AutoDbMatchJob, AutoDbMatchingRun
from apps.autodb.services.lookup_v3_readonly import AutoDbLookupV3ReadOnlyService
from apps.autodb.services.matching.clone_sync_planner import AutoDbCloneSyncPlanner
from apps.autodb.services.matching.enrichment_planner import AutoDbEnrichmentPlanner
from apps.autodb.services.matching.job_builder import AutoDbMatchJobBuilder
from apps.autodb.services.matching.link_audit_adapter import AutoDbLinkAuditAdapter
from apps.autodb.services.matching.local_lookup import AutoDbLocalLookupService
from apps.autodb.services.matching.remote_lookup import AutoDbRemoteLookupService
from apps.autodb.services.matching.safe_link_planner import AutoDbSafeLinkPlanner


@dataclass(frozen=True)
class AutoDbMatchingPreGateProbeRow:
    product_id: str
    supplier_offer_id: str
    raw_brand: str
    resolved_supplier_id: int | None
    source_type: str
    article: str
    lookup_found: bool
    matched_source: str
    local_hits: int
    remote_hits: int
    error: str


@dataclass(frozen=True)
class AutoDbMatchingPreGateResult:
    checked: int
    hits: int
    candidate_count: int
    skipped_missing_supplier_id: int
    hit_rate_pct: float
    min_probe_n: int
    min_hit_rate_pct: float
    can_continue: bool
    would_stop: bool
    reason: str
    rows: tuple[AutoDbMatchingPreGateProbeRow, ...]


@dataclass(frozen=True)
class AutoDbPilotEligibilityResult:
    candidate_count: int
    probe_n: int
    hits: int
    hit_rate_pct: float
    min_probe_n: int
    min_hit_rate_pct: float
    can_continue: bool
    reason: str


class AutoDbMatchingPipelineService:
    """Stage-by-stage orchestrator. Apply stages require explicit command flags."""

    def __init__(
        self,
        *,
        job_builder: AutoDbMatchJobBuilder | None = None,
        local_lookup: AutoDbLocalLookupService | None = None,
        remote_lookup: AutoDbRemoteLookupService | None = None,
        lookup_v3: AutoDbLookupV3ReadOnlyService | None = None,
        clone_planner: AutoDbCloneSyncPlanner | None = None,
        link_audit: AutoDbLinkAuditAdapter | None = None,
        safe_link_planner: AutoDbSafeLinkPlanner | None = None,
        enrichment_planner: AutoDbEnrichmentPlanner | None = None,
    ):
        self.job_builder = job_builder or AutoDbMatchJobBuilder()
        self.local_lookup = local_lookup or AutoDbLocalLookupService()
        self.remote_lookup = remote_lookup or AutoDbRemoteLookupService()
        self.lookup_v3 = lookup_v3 or AutoDbLookupV3ReadOnlyService()
        self.clone_planner = clone_planner or AutoDbCloneSyncPlanner()
        self.link_audit = link_audit or AutoDbLinkAuditAdapter()
        self.safe_link_planner = safe_link_planner or AutoDbSafeLinkPlanner()
        self.enrichment_planner = enrichment_planner or AutoDbEnrichmentPlanner()

    def build_jobs(
        self,
        *,
        run: AutoDbMatchingRun | None,
        supplier_code: str = "",
        limit: int = 100,
        dry_run: bool = True,
        fast_mode: bool = False,
    ):
        return self.job_builder.build_jobs(
            run=run,
            supplier_code=supplier_code,
            limit=limit,
            dry_run=dry_run,
            fast_mode=fast_mode,
        )

    def pre_gate_build_candidates(
        self,
        *,
        supplier_code: str = "",
        build_limit: int = 1000,
        sample_size: int = 10,
        min_probe_n: int = 20,
        min_hit_rate_pct: float = 20.0,
    ) -> AutoDbMatchingPreGateResult:
        rows = self.job_builder.build_jobs(
            run=None,
            supplier_code=supplier_code,
            limit=max(int(build_limit or 0), 1),
            dry_run=True,
            fast_mode=True,
        )
        skipped_missing_supplier_id = sum(1 for item in rows if str(item.reason or "") == "missing_supplier_id")
        candidates = [
            item
            for item in rows
            if item.status == AutoDbMatchJob.STATUS_NEW and item.resolved_supplier_id is not None and bool(str(item.canonical_article or "").strip())
        ]
        sample = candidates[: max(int(sample_size or 0), 1)]

        probe_rows: list[AutoDbMatchingPreGateProbeRow] = []
        hits = 0
        for item in sample:
            result = self.lookup_v3.lookup(brand=item.raw_brand, article=item.canonical_article)
            found = bool(result.found)
            if found:
                hits += 1
            probe_rows.append(
                AutoDbMatchingPreGateProbeRow(
                    product_id=item.product_id,
                    supplier_offer_id=item.supplier_offer_id,
                    raw_brand=item.raw_brand,
                    resolved_supplier_id=item.resolved_supplier_id,
                    source_type=item.article_source_type,
                    article=item.canonical_article,
                    lookup_found=found,
                    matched_source=result.matched_source,
                    local_hits=int(result.local_hits or 0),
                    remote_hits=int(result.remote_hits or 0),
                    error=str(result.error or ""),
                )
            )

        checked = len(sample)
        candidate_count = len(candidates)
        eligibility = self.evaluate_pilot_eligibility(
            candidate_count=candidate_count,
            probe_n=checked,
            hits=hits,
            min_probe_n=min_probe_n,
            min_hit_rate_pct=min_hit_rate_pct,
        )
        if candidate_count <= 0:
            return AutoDbMatchingPreGateResult(
                checked=checked,
                hits=0,
                candidate_count=candidate_count,
                skipped_missing_supplier_id=skipped_missing_supplier_id,
                hit_rate_pct=eligibility.hit_rate_pct,
                min_probe_n=eligibility.min_probe_n,
                min_hit_rate_pct=eligibility.min_hit_rate_pct,
                can_continue=False,
                would_stop=True,
                reason="candidates_zero",
                rows=tuple(probe_rows),
            )
        if not eligibility.can_continue:
            return AutoDbMatchingPreGateResult(
                checked=checked,
                hits=hits,
                candidate_count=candidate_count,
                skipped_missing_supplier_id=skipped_missing_supplier_id,
                hit_rate_pct=eligibility.hit_rate_pct,
                min_probe_n=eligibility.min_probe_n,
                min_hit_rate_pct=eligibility.min_hit_rate_pct,
                can_continue=False,
                would_stop=True,
                reason=eligibility.reason,
                rows=tuple(probe_rows),
            )
        return AutoDbMatchingPreGateResult(
            checked=checked,
            hits=hits,
            candidate_count=candidate_count,
            skipped_missing_supplier_id=skipped_missing_supplier_id,
            hit_rate_pct=eligibility.hit_rate_pct,
            min_probe_n=eligibility.min_probe_n,
            min_hit_rate_pct=eligibility.min_hit_rate_pct,
            can_continue=True,
            would_stop=False,
            reason="ok",
            rows=tuple(probe_rows),
        )

    def evaluate_pilot_eligibility(
        self,
        *,
        candidate_count: int,
        probe_n: int,
        hits: int,
        min_probe_n: int = 20,
        min_hit_rate_pct: float = 20.0,
    ) -> AutoDbPilotEligibilityResult:
        candidates = max(int(candidate_count or 0), 0)
        checked = max(int(probe_n or 0), 0)
        hit_count = max(int(hits or 0), 0)
        min_probe = max(int(min_probe_n or 0), 1)
        min_hit_rate = max(min(float(min_hit_rate_pct or 0.0), 100.0), 0.0)
        hit_rate_pct = (float(hit_count) / float(checked) * 100.0) if checked > 0 else 0.0

        if candidates <= 0:
            return AutoDbPilotEligibilityResult(
                candidate_count=candidates,
                probe_n=checked,
                hits=hit_count,
                hit_rate_pct=hit_rate_pct,
                min_probe_n=min_probe,
                min_hit_rate_pct=min_hit_rate,
                can_continue=False,
                reason="candidates_zero",
            )
        if checked < min_probe:
            return AutoDbPilotEligibilityResult(
                candidate_count=candidates,
                probe_n=checked,
                hits=hit_count,
                hit_rate_pct=hit_rate_pct,
                min_probe_n=min_probe,
                min_hit_rate_pct=min_hit_rate,
                can_continue=False,
                reason="insufficient_probe_n",
            )
        if hit_rate_pct < min_hit_rate:
            return AutoDbPilotEligibilityResult(
                candidate_count=candidates,
                probe_n=checked,
                hits=hit_count,
                hit_rate_pct=hit_rate_pct,
                min_probe_n=min_probe,
                min_hit_rate_pct=min_hit_rate,
                can_continue=False,
                reason="hit_rate_too_low",
            )
        return AutoDbPilotEligibilityResult(
            candidate_count=candidates,
            probe_n=checked,
            hits=hit_count,
            hit_rate_pct=hit_rate_pct,
            min_probe_n=min_probe,
            min_hit_rate_pct=min_hit_rate,
            can_continue=True,
            reason="ok",
        )

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
