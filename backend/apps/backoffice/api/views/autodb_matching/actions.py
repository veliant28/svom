from __future__ import annotations

from dataclasses import asdict

from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from apps.autodb.models import AutoDbMatchJob
from apps.autodb.services.lookup_v3_readonly import AutoDbLookupV3ReadOnlyService
from apps.autodb.tasks import manual_bind_product_to_autodb_task
from apps.catalog.models import Product
from apps.autodb.services.matching import (
    AutoDbCloneSyncPlanner,
    AutoDbEnrichmentPlanner,
    AutoDbLinkAuditAdapter,
    AutoDbMatchJobBuilder,
    AutoDbSafeLinkPlanner,
)

from .._base import BackofficeAPIView
from .search import ManualAutoDbSearch, remote_result_payload
from .utils import (
    PROTECTED_FIELDS,
    jobs_for_action,
    parse_bool,
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
        article = safe_str(request.data.get("article"))
        if not article:
            return Response({"detail": "article is required"}, status=status.HTTP_400_BAD_REQUEST)

        supplier_id = parse_supplier_id(request.data.get("supplier_id") or request.data.get("autodb_supplier_id"))
        if supplier_id is None:
            helper = ManualAutoDbSearch()
            candidates = helper.local_candidates(article=article)
            if not candidates:
                candidates = self._history_candidates(article=article, variants=helper.variants(article))
            return Response({"dry_run": True, "source": "local", "quota": quota_payload(), "candidates": candidates, "results": []})

        supplier_name = safe_str(request.data.get("supplier_name")) or supplier_display_name(supplier_id)
        result = ManualAutoDbSearch().local(supplier_id=supplier_id, supplier_name=supplier_name, article=article)
        return Response({"dry_run": True, "source": "local", "quota": quota_payload(), "results": [result]})

    def _history_candidates(self, *, article: str, variants: list[str], limit: int = 80) -> list[dict]:
        normalized_values = {safe_str(article).upper()}
        normalized_values.update({safe_str(item).upper() for item in variants if safe_str(item)})
        normalized_values.discard("")
        if not normalized_values:
            return []

        jobs = (
            AutoDbMatchJob.objects.exclude(resolved_supplier_id__isnull=True)
            .filter(
                Q(canonical_article__in=normalized_values)
                | Q(article_value__in=normalized_values)
            )
            .order_by("-updated_at")[:300]
        )

        buckets: dict[tuple[int, str], dict] = {}
        for job in jobs:
            supplier_id = int(job.resolved_supplier_id or 0)
            if supplier_id <= 0:
                continue
            matched_article = safe_str(job.canonical_article or job.article_value).upper()
            if not matched_article:
                continue
            key = (supplier_id, matched_article)
            if key not in buckets:
                buckets[key] = {
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_display_name(supplier_id, job.raw_brand),
                    "matched_stored_article": matched_article,
                    "hits": 0,
                    "matched_table": "jobs_history",
                }
            buckets[key]["hits"] = int(buckets[key]["hits"]) + 1

        ordered = sorted(
            buckets.values(),
            key=lambda item: (-int(item["hits"]), safe_str(item["supplier_name"]), int(item["supplier_id"])),
        )
        return ordered[: max(int(limit), 1)]


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

        article_lookup = self._extract_article_from_brand_prefixed_input(article=article, brand=brand)
        helper = ManualAutoDbSearch()
        variants = helper.variants(article_lookup)
        if quota["paused"]:
            return Response({"dry_run": True, "source": "remote", "quota": quota, "results": [self._quota_row(supplier_id, brand, article_lookup, variants)]})
        try:
            result = AutoDbLookupV3ReadOnlyService().lookup(brand=brand, article=article_lookup)
        except Exception as exc:  # noqa: BLE001
            return Response({"dry_run": True, "source": "remote", "quota": quota, "results": [self._error_row(supplier_id, brand, article_lookup, variants, exc)]})
        previews: dict | None = None
        try:
            supplier_id_value = getattr(result, "supplier_id", None)
            article_value = safe_str(getattr(result, "remote_stored_article", "")) or safe_str(getattr(result, "canonical_article", ""))
            if bool(getattr(result, "found", False)) and supplier_id_value and article_value:
                previews = helper.build_remote_previews(
                    supplier_id=int(supplier_id_value),
                    article_number=article_value,
                )
        except Exception:  # noqa: BLE001
            previews = None
        return Response(
            {
                "dry_run": True,
                "source": "remote",
                "quota": quota_payload(),
                "results": [remote_result_payload(result, article=article_lookup, variants=variants, previews=previews)],
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

    def _extract_article_from_brand_prefixed_input(self, *, article: str, brand: str) -> str:
        raw = " ".join(safe_str(article).split())
        if not raw:
            return ""
        brand_norm = safe_str(brand).upper()
        tokens = raw.split(" ")
        if len(tokens) <= 1 or not brand_norm:
            return raw
        first = safe_str(tokens[0]).upper()
        last = safe_str(tokens[-1]).upper()
        if first == brand_norm and len(tokens) > 1:
            return " ".join(tokens[1:]).strip()
        if last == brand_norm and len(tokens) > 1:
            return " ".join(tokens[:-1]).strip()
        return raw

class BackofficeAutoDbMatchingProductLookupAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def get(self, request):
        query = safe_str(request.query_params.get("q"))
        limit = parse_positive_int(request.query_params.get("limit"), default=8, maximum=20)
        if len(query) < 2:
            return Response({"count": 0, "results": []})

        qs = (
            Product.objects.filter(
                Q(svom_sku__icontains=query)
                | Q(sku__icontains=query)
                | Q(name__icontains=query)
                | Q(display_brand_name__icontains=query)
            )
            .order_by("-updated_at")[:limit]
        )
        rows = [
            {
                "id": str(item.id),
                "sku": safe_str(item.sku),
                "svom_sku": safe_str(item.svom_sku),
                "article": safe_str(item.article),
                "name": safe_str(item.name),
                "brand_name": safe_str(item.display_brand_name or item.autodb_supplier_name or ""),
            }
            for item in qs
        ]
        return Response({"count": len(rows), "results": rows})


class BackofficeAutoDbMatchingManualSearchCreateJobAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        product_id = safe_str(request.data.get("product_id"))
        supplier_id = parse_supplier_id(request.data.get("supplier_id") or request.data.get("autodb_supplier_id"))
        article = safe_str(request.data.get("article"))
        supplier_name = safe_str(request.data.get("supplier_name"))
        dispatch_async_raw = request.data.get("dispatch_async")
        if isinstance(dispatch_async_raw, bool):
            parsed_async = dispatch_async_raw
        else:
            parsed_async = parse_bool(dispatch_async_raw)
        dispatch_async = True if parsed_async is None else bool(parsed_async)

        if not product_id:
            return Response({"detail": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if supplier_id is None:
            return Response({"detail": "supplier_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not article:
            return Response({"detail": "article is required"}, status=status.HTTP_400_BAD_REQUEST)

        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            return Response({"detail": "product not found"}, status=status.HTTP_404_NOT_FOUND)

        if dispatch_async:
            task = manual_bind_product_to_autodb_task.delay(
                product_id=str(product.id),
                supplier_id=int(supplier_id),
                article_number=article,
                supplier_name=supplier_name,
                article_id=None,
                actor_id=str(getattr(request.user, "id", "") or ""),
            )
            return Response(
                {
                    "dry_run": False,
                    "created": True,
                    "status": "queued",
                    "mode": "async",
                    "task_id": str(task.id),
                    "message": "Manual bind queued.",
                    "result": {
                        "product_id": str(product.id),
                        "supplier_id": int(supplier_id),
                        "article_number": article,
                    },
                },
                status=status.HTTP_202_ACCEPTED,
            )

        result = manual_bind_product_to_autodb_task(
            product_id=str(product.id),
            supplier_id=int(supplier_id),
            article_number=article,
            supplier_name=supplier_name,
            article_id=None,
            actor_id=str(getattr(request.user, "id", "") or ""),
        )
        status_value = safe_str(result.get("status")) if isinstance(result, dict) else ""
        response_status = status.HTTP_200_OK if status_value == "bound" else status.HTTP_422_UNPROCESSABLE_ENTITY
        return Response(
            {
                "dry_run": False,
                "created": bool(status_value == "bound"),
                "status": status_value or "error",
                "mode": "sync",
                "protected_fields": PROTECTED_FIELDS,
                "message": "Manual bind completed." if status_value == "bound" else "Manual bind failed.",
                "result": result if isinstance(result, dict) else {},
            },
            status=response_status,
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
