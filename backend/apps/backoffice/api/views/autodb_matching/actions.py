from __future__ import annotations

from dataclasses import asdict

from rest_framework import status
from rest_framework.response import Response

from apps.autodb.models import AutoDbRemoteQuotaState
from apps.autodb.services.lookup_v3_readonly import AutoDbLookupV3ReadOnlyService
from apps.autodb.services.matching import (
    AutoDbCloneSyncPlanner,
    AutoDbEnrichmentPlanner,
    AutoDbLinkAuditAdapter,
    AutoDbMatchJobBuilder,
    AutoDbSafeLinkPlanner,
)
from apps.autodb.services.matching.constants import REMOTE_QUOTA_KEY
from apps.autodb.services.matching.quota_tracker import AutoDbRemoteQuotaTracker

from .._base import BackofficeAPIView
from .search import ManualAutoDbSearch, remote_result_payload
from .utils import (
    PROTECTED_FIELDS,
    jobs_for_action,
    parse_positive_int,
    parse_supplier_id,
    quota_payload,
    safe_str,
    supplier_display_name,
)


class BackofficeAutoDbMatchingBuildJobsDryRunAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        rows = AutoDbMatchJobBuilder().build_jobs(
            supplier_code=safe_str(request.data.get("supplier_code")),
            limit=parse_positive_int(request.data.get("limit"), default=100, maximum=500),
            dry_run=True,
        )
        return Response({"dry_run": True, "created": False, "count": len(rows), "results": [asdict(item) for item in rows]})


class BackofficeAutoDbMatchingRunLocalDryRunAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        helper = ManualAutoDbSearch()
        rows: list[dict] = []
        for job in jobs_for_action(request):
            if not job.resolved_supplier_id:
                rows.append({"job_id": str(job.id), "status": "skipped", "reason": "missing Auto_DB supplier_id"})
                continue
            rows.append(
                {
                    "job_id": str(job.id),
                    **helper.local(
                        supplier_id=int(job.resolved_supplier_id),
                        supplier_name=supplier_display_name(int(job.resolved_supplier_id), job.raw_brand),
                        article=job.canonical_article or job.article_value,
                    ),
                }
            )
        return Response({"dry_run": True, "count": len(rows), "results": rows})


class BackofficeAutoDbMatchingRunRemoteAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        quota = quota_payload()
        if quota["paused"]:
            return Response({"dry_run": True, "status": "quota_paused", "quota": quota, "results": []})
        return Response(
            {
                "dry_run": True,
                "status": "planned",
                "quota": quota,
                "results": [],
                "message": "Remote batch lookup is blocked in this UI task; use manual remote search or future confirmed endpoint.",
                "protected_fields": PROTECTED_FIELDS,
            }
        )


class BackofficeAutoDbMatchingManualSearchLocalAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        supplier_id = parse_supplier_id(request.data.get("supplier_id") or request.data.get("autodb_supplier_id"))
        article = safe_str(request.data.get("article"))
        if supplier_id is None or not article:
            return Response({"detail": "supplier_id and article are required"}, status=status.HTTP_400_BAD_REQUEST)
        supplier_name = safe_str(request.data.get("supplier_name")) or supplier_display_name(supplier_id)
        result = ManualAutoDbSearch().local(supplier_id=supplier_id, supplier_name=supplier_name, article=article)
        return Response({"dry_run": True, "source": "local", "quota": quota_payload(), "results": [result]})


class BackofficeAutoDbMatchingManualSearchRemoteAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        quota = quota_payload()
        article = safe_str(request.data.get("article"))
        supplier_id = parse_supplier_id(request.data.get("supplier_id") or request.data.get("autodb_supplier_id"))
        brand = safe_str(request.data.get("brand") or request.data.get("supplier_name"))
        if supplier_id and not brand:
            brand = supplier_display_name(supplier_id)
        if not article or not brand:
            return Response({"detail": "brand/supplier and article are required"}, status=status.HTTP_400_BAD_REQUEST)

        helper = ManualAutoDbSearch()
        variants = helper.variants(article)
        if quota["paused"]:
            return Response({"dry_run": True, "source": "remote", "quota": quota, "results": [self._quota_row(supplier_id, brand, article, variants)]})
        try:
            result = AutoDbLookupV3ReadOnlyService().lookup(brand=brand, article=article)
        except Exception as exc:  # noqa: BLE001
            if self._is_quota_error(exc):
                AutoDbRemoteQuotaTracker().record_quota_error(
                    self._quota_state(),
                    error=str(exc),
                    cooldown_minutes=60,
                    run_id="manual-search",
                )
            return Response({"dry_run": True, "source": "remote", "quota": quota, "results": [self._error_row(supplier_id, brand, article, variants, exc)]})
        AutoDbRemoteQuotaTracker().record_success(
            self._quota_state(),
            query_count=int(getattr(result, "remote_queries", 0) or 0) + 1,
            run_id="manual-search",
        )
        return Response(
            {
                "dry_run": True,
                "source": "remote",
                "quota": quota_payload(),
                "results": [remote_result_payload(result, article=article, variants=variants)],
            }
        )

    def _quota_row(self, supplier_id: int | None, brand: str, article: str, variants: list[str]) -> dict:
        return {
            "source": "remote",
            "supplier_id": supplier_id,
            "supplier_name": brand,
            "article_input": article,
            "variants": variants,
            "status": "quota_paused",
            "reason": "remote quota cooldown active",
            "image_thumbnails": [],
        }

    def _error_row(self, supplier_id: int | None, brand: str, article: str, variants: list[str], exc: Exception) -> dict:
        return {
            "source": "remote",
            "supplier_id": supplier_id,
            "supplier_name": brand,
            "article_input": article,
            "variants": variants,
            "status": "error",
            "reason": safe_str(exc),
            "image_thumbnails": [],
        }

    def _quota_state(self):
        quota, _created = AutoDbRemoteQuotaState.objects.get_or_create(remote_key=REMOTE_QUOTA_KEY)
        return quota

    def _is_quota_error(self, value: object) -> bool:
        text = str(value or "").lower()
        return "error 1226" in text or "max_questions" in text or "quota" in text


class BackofficeAutoDbMatchingManualSearchCreateJobAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        return Response(
            {
                "dry_run": True,
                "created": False,
                "status": "planned",
                "protected_fields": PROTECTED_FIELDS,
                "message": "Matching job creation is a dry-run placeholder in this UI task.",
                "payload": {
                    "product_id": safe_str(request.data.get("product_id")),
                    "supplier_id": parse_supplier_id(request.data.get("supplier_id")),
                    "article": safe_str(request.data.get("article")),
                    "source_result": request.data.get("result") if isinstance(request.data.get("result"), dict) else {},
                },
            }
        )


class BackofficeAutoDbMatchingPlanCloneSyncAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        rows = AutoDbCloneSyncPlanner().plan_jobs(jobs_for_action(request), dry_run=True)
        return self._rows(rows)

    def _rows(self, rows):
        return Response({"dry_run": True, "count": len(rows), "results": [asdict(item) for item in rows], "protected_fields": PROTECTED_FIELDS})


class BackofficeAutoDbMatchingAuditLinkAPIView(BackofficeAutoDbMatchingPlanCloneSyncAPIView):
    def post(self, request):
        rows = [AutoDbLinkAuditAdapter().audit_job(job, dry_run=True) for job in jobs_for_action(request)]
        return self._rows(rows)


class BackofficeAutoDbMatchingPlanSafeLinkAPIView(BackofficeAutoDbMatchingPlanCloneSyncAPIView):
    def post(self, request):
        rows = AutoDbSafeLinkPlanner().plan_jobs(jobs_for_action(request), dry_run=True)
        return self._rows(rows)


class BackofficeAutoDbMatchingPlanEnrichmentAPIView(BackofficeAutoDbMatchingPlanCloneSyncAPIView):
    def post(self, request):
        rows = AutoDbEnrichmentPlanner().plan_jobs(jobs_for_action(request), dry_run=True)
        return self._rows(rows)
