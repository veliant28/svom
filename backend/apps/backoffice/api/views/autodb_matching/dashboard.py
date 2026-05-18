from __future__ import annotations

from django.db.models import Count, Exists, F, Q
from django.utils import timezone
from rest_framework.response import Response

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob, AutoDbMatchingRun
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.compatibility.models import ProductFitment

from .._base import BackofficeAPIView
from .jobs import BackofficeAutoDbMatchingJobsAPIView
from .utils import PROTECTED_FIELDS, iso_or_none, quota_payload, safe_str, status_counts, supplier_display_name, trusted_link_exists_queryset

BACKOFFICE_TECDOC_BATCH_RUN_TYPE = "backoffice_tecdoc_batch_bind"


class BackofficeAutoDbMatchingDashboardAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def get(self, request):
        jobs = AutoDbMatchJob.objects.all()
        today = timezone.localdate()
        latest_run = (
            AutoDbMatchingRun.objects.filter(run_type=BACKOFFICE_TECDOC_BATCH_RUN_TYPE)
            .order_by("-created_at")
            .first()
        )
        trusted_exists = trusted_link_exists_queryset()
        unlinked_products = Product.objects.annotate(_trusted=Exists(trusted_exists)).filter(_trusted=False).count()
        source_rows = list(jobs.values("supplier_code").annotate(count=Count("id")).order_by("supplier_code"))
        brand_rows = list(
            Product.objects.exclude(autodb_supplier_id__isnull=True)
            .values("autodb_supplier_id")
            .annotate(count=Count("id"))
            .order_by("-count")[:8]
        )
        quota = quota_payload()
        latest_summary = latest_run.summary_json if latest_run and isinstance(latest_run.summary_json, dict) else {}

        return Response(
            {
                "cards": self._cards(jobs=jobs, unlinked_products=unlinked_products, latest_run=latest_run, today=today, quota=quota),
                "jobs_by_status": status_counts(jobs),
                "brand_coverage_distribution": self._brand_distribution(brand_rows),
                "matching_funnel": self._fallback_products_funnel(),
                "source_breakdown": [
                    {"source": safe_str(item["supplier_code"]) or "product_catalog", "count": int(item["count"] or 0)}
                    for item in source_rows
                ],
                "remote_quota_usage": [{"label": quota["remote_key"], "used": quota["estimated_queries_used"], "paused": quota["paused"]}],
                "quota": quota,
                "latest_run": self._latest_run(latest_run=latest_run, latest_summary=latest_summary, quota=quota),
                "safety": {
                    **PROTECTED_FIELDS,
                    "product_links_applied": False,
                    "enrichment_applied": False,
                    "images_applied": False,
                    "imports_used": False,
                    "utr_api_used": False,
                    "price_stock_changed": False,
                },
            }
        )

    def _cards(self, *, jobs, unlinked_products: int, latest_run, today, quota: dict) -> dict:
        total_brands_in_products = Product.objects.exclude(normalized_brand="").values("normalized_brand").distinct().count()
        mapped_brands_in_products = Product.objects.exclude(autodb_supplier_id__isnull=True).values("autodb_supplier_id").distinct().count()
        linked_products_count = (
            Product.objects.exclude(autodb_supplier_id__isnull=True)
            .exclude(autodb_article_number__isnull=True)
            .exclude(autodb_article_number="")
            .exclude(autodb_article_key__isnull=True)
            .exclude(autodb_article_key="")
            .count()
        )
        return {
            "total_jobs": jobs.count(),
            "mapped_brands": mapped_brands_in_products,
            "total_brands": total_brands_in_products,
            "unlinked_products": unlinked_products,
            "linked_products": linked_products_count,
            "total_products": Product.objects.count(),
            "safe_link_candidates": jobs.filter(status=AutoDbMatchJob.STATUS_SAFE_LINK_CANDIDATE).count(),
            "needs_review": jobs.filter(status=AutoDbMatchJob.STATUS_NEEDS_REVIEW).count(),
            "quota_paused": jobs.filter(status=AutoDbMatchJob.STATUS_QUOTA_PAUSED).count() + (1 if quota["paused"] else 0),
            "linked_today": jobs.filter(status=AutoDbMatchJob.STATUS_LINKED, updated_at__date=today).count(),
            "latest_run": latest_run.run_type if latest_run else "",
            "product_attribute_planned": AutoDbMatchEvidence.objects.filter(stage="enrichment_plan").count(),
            # catalog_productattribute table is removed; attribute source is Auto_DB clone only.
            "product_attribute_applied": 0,
            "product_fitment_planned": AutoDbMatchEvidence.objects.filter(stage="enrichment_plan").count(),
            "product_fitment_applied": ProductFitment.objects.filter(source=ProductFitment.SOURCE_AUTODB_PRO).count(),
        }

    def _brand_distribution(self, rows: list[dict]) -> list[dict]:
        return [
            {
                "label": supplier_display_name(int(item["autodb_supplier_id"])),
                "value": int(item["count"] or 0),
            }
            for item in rows
        ]

    def _latest_run(self, *, latest_run, latest_summary: dict, quota: dict) -> dict:
        return {
            "id": str(latest_run.id) if latest_run else "",
            "status": latest_run.status if latest_run else "",
            "started_at": iso_or_none(latest_run.started_at) if latest_run else None,
            "finished_at": iso_or_none(latest_run.finished_at) if latest_run else None,
            "checked": int(latest_summary.get("checked") or latest_summary.get("rows_count") or 0),
            "hits": int(latest_summary.get("hits") or 0),
            "safe_candidates": int(latest_summary.get("safe_candidates") or 0),
            "errors": int(latest_summary.get("errors") or latest_summary.get("errors_count") or 0),
            "quota_status": "paused" if quota["paused"] else "ok",
            "links_applied": int(latest_summary.get("links_applied") or 0),
            "enrichment_applied": int(latest_summary.get("enrichment_applied") or 0),
        }

    def _fallback_products_funnel(self) -> list[dict]:
        helper = BackofficeAutoDbMatchingJobsAPIView()
        queryset = Product.objects.all()

        new_count = (
            helper._exclude_explicit_non_tecdoc_brands(queryset)
            .filter(Q(article__isnull=False) & ~Q(article=""))
            .filter(Q(autodb_article_key__isnull=True) | Q(autodb_article_key=""))
            .count()
        )
        local_found_count = helper._filter_fallback_local_found_queryset(queryset).count()
        linked_count = helper._filter_fallback_linked_queryset(queryset).count()
        needs_review_count = queryset.filter(
            autodb_link_qualities__status=AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
        ).distinct().count()
        skipped_non_tecdoc_count = helper._only_explicit_non_tecdoc_brands(queryset).count()
        bad_article_source_count = queryset.filter(Q(article__isnull=True) | Q(article="")).count()

        return [
            {"stage": AutoDbMatchJob.STATUS_NEW, "count": int(new_count)},
            {"stage": AutoDbMatchJob.STATUS_LOCAL_FOUND, "count": int(local_found_count)},
            {"stage": AutoDbMatchJob.STATUS_LINKED, "count": int(linked_count)},
            {"stage": AutoDbMatchJob.STATUS_NEEDS_REVIEW, "count": int(needs_review_count)},
            {"stage": AutoDbMatchJob.STATUS_SKIPPED_NON_TECDOC, "count": int(skipped_non_tecdoc_count)},
            {"stage": AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE, "count": int(bad_article_source_count)},
        ]
