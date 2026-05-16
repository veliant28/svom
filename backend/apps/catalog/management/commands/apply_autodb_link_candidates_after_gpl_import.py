from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.autodb.services.article_enrichment import AutoDbArticleEnrichmentService
from apps.autodb.services.product_attribute_enrichment import AutoDbProductAttributeEnrichmentService
from apps.autodb.services.product_fitment_enrichment import AutoDbProductFitmentEnrichmentService
from apps.autodb.services.product_image_enrichment import AutoDbProductImageEnrichmentService
from apps.autodb.services.product_name_enrichment import AutoDbProductNameEnrichmentService
from apps.catalog.models import AutoDbProductLinkQuality, Product


class Command(BaseCommand):
    help = "Safe apply for audited Auto-DB link candidates after GPL import (dry-run or real apply)."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier code, e.g. GPL")
        parser.add_argument("--candidates-csv", type=str, required=True, help="Input audit CSV path")
        parser.add_argument("--only-safe", action="store_true", help="Process only decision=safe_link_candidate")
        parser.add_argument("--dry-run", action="store_true", help="Run without writes")
        parser.add_argument("--apply", action="store_true", help="Apply link writes")
        parser.add_argument(
            "--skip-post-enrichment",
            action="store_true",
            help="Skip post-link enrichment (name/fitment/attributes/images) during apply mode.",
        )
        parser.add_argument("--limit", type=int, default=0, help="Limit rows after filters (0 = all)")
        parser.add_argument("--export-csv", type=str, required=True, help="Output dry-run csv path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier")
        dry_run = bool(options.get("dry_run"))
        do_apply = bool(options.get("apply"))
        skip_post_enrichment = bool(options.get("skip_post_enrichment"))
        post_enrichment_enabled = do_apply and not skip_post_enrichment
        only_safe = bool(options.get("only_safe"))
        limit = max(int(options.get("limit") or 0), 0)
        input_path = Path(str(options.get("candidates_csv") or "")).expanduser()
        output_path = Path(str(options.get("export_csv") or "")).expanduser()
        if not input_path.exists():
            raise CommandError(f"Candidates CSV not found: {input_path}")
        if dry_run == do_apply:
            raise CommandError("Specify exactly one mode: --dry-run or --apply.")
        if not only_safe:
            raise CommandError("This command requires --only-safe for guarded GPL link apply.")

        rows = list(csv.DictReader(input_path.open(encoding="utf-8")))
        if not rows:
            raise CommandError("Candidates CSV is empty.")

        products_by_id = {
            str(item.id): item
            for item in Product.objects.filter(id__in=[str(row.get("product_id") or "").strip() for row in rows])
            .only(
                "id",
                "name",
                "category_id",
                "name_manually_locked",
                "category_manually_locked",
                "brand_manually_locked",
                "autodb_supplier_id",
                "autodb_article_number",
                "autodb_article_key",
            )
        }

        row_ids_for_selection = self._select_row_ids(rows=rows, only_safe=only_safe, limit=limit)
        out_rows: list[dict[str, str]] = []
        counters = {
            "candidates_total": len(rows),
            "safe_candidates": 0,
            "selected_for_run": len(row_ids_for_selection),
            "would_link": 0,
            "applied_links": 0,
            "created_new_links": 0,
            "updated_incomplete_link_fields": 0,
            "skipped_already_complete_link": 0,
            "skipped_not_safe": 0,
            "skipped_conflict": 0,
            "skipped_manual_locked": 0,
            "skipped_by_limit": 0,
            "would_update_product_autodb_fields": 0,
            "would_create_quality_rows": 0,
            "updated_quality_rows": 0,
            "unchanged_quality_rows": 0,
            "failed": 0,
            "would_change_name": 0,
            "would_change_category": 0,
            "would_change_images": 0,
            "would_change_primary_image": 0,
            "post_enrichment_attempted": 0,
            "post_enrichment_ok": 0,
            "post_enrichment_partial": 0,
            "post_enrichment_failed": 0,
            "post_enrichment_name_updated": 0,
            "post_enrichment_fitments_created": 0,
            "post_enrichment_fitments_updated": 0,
            "post_enrichment_attributes_created": 0,
            "post_enrichment_attributes_updated": 0,
            "post_enrichment_images_created": 0,
            "post_enrichment_images_stale_marked": 0,
        }

        existing_quality_keys = {
            (str(product_id), str(article_key or ""))
            for product_id, article_key in AutoDbProductLinkQuality.objects.filter(
                product_id__in=list(products_by_id.keys())
            ).values_list("product_id", "autodb_article_key")
        }

        for index, row in enumerate(rows):
            row_id = self._row_id(index=index, row=row)
            product_id = str(row.get("product_id") or "").strip()
            decision = str(row.get("decision") or "").strip()
            reason = str(row.get("reason") or "").strip()
            blocker_type = str(row.get("blocker_type") or "").strip()
            brand_score = float(str(row.get("brand_match_score") or "0") or 0)
            article_score = float(str(row.get("article_match_score") or "0") or 0)
            semantic_score = float(str(row.get("semantic_score") or "0") or 0)
            category_score = float(str(row.get("category_compatibility_score") or "0") or 0)
            supplier_id = str(row.get("candidate_autodb_supplier_id") or "").strip()
            article_number = str(row.get("candidate_autodb_article_number") or "").strip()
            article_key = f"{supplier_id}:{article_number}" if supplier_id and article_number else ""

            if decision == "safe_link_candidate":
                counters["safe_candidates"] += 1

            action = "skip"
            skip_reason = ""
            if row_id not in row_ids_for_selection:
                if decision == "safe_link_candidate" or not only_safe:
                    counters["skipped_by_limit"] += 1
                    action = "skip_limit"
                    skip_reason = "limit_not_selected"
                elif only_safe and decision != "safe_link_candidate":
                    counters["skipped_not_safe"] += 1
                    action = "skip_not_safe"
                    skip_reason = "only_safe_mode"
                else:
                    counters["skipped_not_safe"] += 1
                    action = "skip_not_safe"
                    skip_reason = "decision_not_safe"
            elif only_safe and decision != "safe_link_candidate":
                counters["skipped_not_safe"] += 1
                action = "skip_not_safe"
                skip_reason = "only_safe_mode"
            elif decision != "safe_link_candidate":
                counters["skipped_not_safe"] += 1
                action = "skip_not_safe"
                skip_reason = "decision_not_safe"
            elif brand_score < 0.8 or article_score < 0.95 or semantic_score < 1.0 or category_score < 0.7:
                counters["skipped_conflict"] += 1
                action = "skip_conflict"
                skip_reason = "threshold_guard_failed"
            elif blocker_type:
                counters["skipped_conflict"] += 1
                action = "skip_conflict"
                skip_reason = f"blocker:{blocker_type}"
            else:
                product = products_by_id.get(product_id)
                if product is None:
                    counters["skipped_not_safe"] += 1
                    action = "skip_not_found"
                    skip_reason = "product_not_found"
                elif bool(product.name_manually_locked) or bool(product.category_manually_locked) or bool(product.brand_manually_locked):
                    counters["skipped_manual_locked"] += 1
                    action = "skip_manual_locked"
                    skip_reason = "manual_lock"
                else:
                    existing_key = str(getattr(product, "autodb_article_key", "") or "").strip()
                    existing_supplier_id = getattr(product, "autodb_supplier_id", None)
                    existing_article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
                    existing_canonical = (
                        f"{int(existing_supplier_id)}:{existing_article_number}"
                        if existing_supplier_id and existing_article_number
                        else ""
                    )
                    has_complete_existing_link = bool(
                        existing_key and existing_supplier_id and existing_article_number and existing_key == existing_canonical
                    )
                    has_any_existing_link = bool(existing_key or existing_supplier_id or existing_article_number)

                    if has_complete_existing_link:
                        counters["skipped_already_complete_link"] += 1
                        action = "skip_already_complete_link"
                        skip_reason = "already_complete_link"
                    else:
                        if has_any_existing_link:
                            counters["updated_incomplete_link_fields"] += 1
                        else:
                            counters["created_new_links"] += 1

                        if (product_id, article_key) not in existing_quality_keys and article_key:
                            counters["would_create_quality_rows"] += 1

                        counters["would_link"] += 1
                        counters["would_update_product_autodb_fields"] += 1
                        action = "would_link" if dry_run else "applied_link"
                        skip_reason = ""
                        if do_apply:
                            try:
                                quality_change = self._apply_link(
                                    product=product,
                                    supplier_id=supplier_id,
                                    article_number=article_number,
                                    article_key=article_key,
                                    reason=reason,
                                    row=row,
                                )
                                counters["applied_links"] += 1
                                if quality_change == "updated":
                                    counters["updated_quality_rows"] += 1
                                elif quality_change == "created":
                                    counters["updated_quality_rows"] += 1
                                else:
                                    counters["unchanged_quality_rows"] += 1
                                if post_enrichment_enabled:
                                    counters["post_enrichment_attempted"] += 1
                                    enrichment = self._run_post_link_enrichment(product=product)
                                    status = str(enrichment.get("status") or "")
                                    if status == "ok":
                                        counters["post_enrichment_ok"] += 1
                                    elif status == "partial":
                                        counters["post_enrichment_partial"] += 1
                                    else:
                                        counters["post_enrichment_failed"] += 1
                                    if str(enrichment.get("name_status") or "") == "updated":
                                        counters["post_enrichment_name_updated"] += 1
                                    counters["post_enrichment_fitments_created"] += int(enrichment.get("fitments_created") or 0)
                                    counters["post_enrichment_fitments_updated"] += int(enrichment.get("fitments_updated") or 0)
                                    counters["post_enrichment_attributes_created"] += int(
                                        enrichment.get("attributes_created") or 0
                                    )
                                    counters["post_enrichment_attributes_updated"] += int(
                                        enrichment.get("attributes_updated") or 0
                                    )
                                    counters["post_enrichment_images_created"] += int(enrichment.get("images_created") or 0)
                                    counters["post_enrichment_images_stale_marked"] += int(
                                        enrichment.get("images_stale_marked") or 0
                                    )
                            except Exception:
                                counters["failed"] += 1
                                action = "failed"
                                skip_reason = "apply_exception"

            out_rows.append(
                {
                    "product_id": product_id,
                    "decision": decision,
                    "reason": reason,
                    "blocker_type": blocker_type,
                    "brand_match_score": str(row.get("brand_match_score") or ""),
                    "article_match_score": str(row.get("article_match_score") or ""),
                    "semantic_score": str(row.get("semantic_score") or ""),
                    "category_compatibility_score": str(row.get("category_compatibility_score") or ""),
                    "candidate_autodb_supplier_id": supplier_id,
                    "candidate_autodb_article_number": article_number,
                    "mapped_site_category": str(row.get("mapped_site_category") or ""),
                    "raw_name": str(row.get("raw_name") or ""),
                    "raw_category": str(row.get("raw_category") or ""),
                    "action": action,
                    "skip_reason": skip_reason,
                    "would_change_name": "0",
                    "would_change_category": "0",
                    "would_change_primary_image": "0",
                    "would_change_price_stock": "0",
                }
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "product_id",
                    "decision",
                    "reason",
                    "blocker_type",
                    "brand_match_score",
                    "article_match_score",
                    "semantic_score",
                    "category_compatibility_score",
                    "candidate_autodb_supplier_id",
                    "candidate_autodb_article_number",
                    "mapped_site_category",
                    "raw_name",
                    "raw_category",
                    "action",
                    "skip_reason",
                    "would_change_name",
                    "would_change_category",
                    "would_change_primary_image",
                    "would_change_price_stock",
                ],
            )
            writer.writeheader()
            for item in out_rows:
                writer.writerow(item)

        mode = "dry-run" if dry_run else "apply"
        self.stdout.write(f"apply_autodb_link_candidates_after_gpl_import {mode} summary:")
        for key in (
            "candidates_total",
            "safe_candidates",
            "selected_for_run",
            "would_link",
            "applied_links",
            "created_new_links",
            "updated_incomplete_link_fields",
            "skipped_already_complete_link",
            "skipped_not_safe",
            "skipped_conflict",
            "skipped_manual_locked",
            "skipped_by_limit",
            "would_update_product_autodb_fields",
            "would_create_quality_rows",
            "updated_quality_rows",
            "unchanged_quality_rows",
            "failed",
            "would_change_name",
            "would_change_category",
            "would_change_images",
            "would_change_primary_image",
            "post_enrichment_attempted",
            "post_enrichment_ok",
            "post_enrichment_partial",
            "post_enrichment_failed",
            "post_enrichment_name_updated",
            "post_enrichment_fitments_created",
            "post_enrichment_fitments_updated",
            "post_enrichment_attributes_created",
            "post_enrichment_attributes_updated",
            "post_enrichment_images_created",
            "post_enrichment_images_stale_marked",
        ):
            self.stdout.write(f"- {key}: {counters[key]}")
        self.stdout.write("- price/stock changed=0")
        self.stdout.write("- UTR calls=0")
        self.stdout.write(f"- export_csv: {output_path}")

    @staticmethod
    def _row_id(*, index: int, row: dict[str, str]) -> str:
        product_id = str(row.get("product_id") or "").strip()
        return f"{index}:{product_id}"

    def _select_row_ids(self, *, rows: list[dict[str, str]], only_safe: bool, limit: int) -> set[str]:
        candidate_ids: list[str] = []
        for index, row in enumerate(rows):
            decision = str(row.get("decision") or "").strip()
            if only_safe and decision != "safe_link_candidate":
                continue
            candidate_ids.append(self._row_id(index=index, row=row))
        if limit > 0:
            candidate_ids = candidate_ids[:limit]
        return set(candidate_ids)

    @transaction.atomic
    def _apply_link(
        self,
        *,
        product: Product,
        supplier_id: str,
        article_number: str,
        article_key: str,
        reason: str,
        row: dict[str, str],
    ) -> str:
        if not supplier_id or not article_number or not article_key:
            return "unchanged"
        product.autodb_supplier_id = int(supplier_id)
        product.autodb_article_number = article_number
        product.autodb_article_key = article_key
        product.save(update_fields=["autodb_supplier_id", "autodb_article_number", "autodb_article_key", "updated_at"])

        evidence = {
            "source": "apply_autodb_link_candidates_after_gpl_import",
            "decision": str(row.get("decision") or ""),
            "reason": reason,
            "brand_match_score": str(row.get("brand_match_score") or ""),
            "article_match_score": str(row.get("article_match_score") or ""),
            "semantic_score": str(row.get("semantic_score") or ""),
            "category_compatibility_score": str(row.get("category_compatibility_score") or ""),
            "autodb_article_title": str(row.get("candidate_autodb_title") or ""),
            "autodb_group": str(row.get("candidate_autodb_group") or ""),
        }
        quality, _ = AutoDbProductLinkQuality.objects.get_or_create(
            product=product,
            autodb_article_key=article_key,
            defaults={
                "autodb_supplier_id": int(supplier_id),
                "autodb_article_number": article_number,
                "status": AutoDbProductLinkQuality.STATUS_TRUSTED,
                "reason": f"safe_apply:{reason}",
                "evidence": evidence,
                "checked_at": timezone.now(),
            },
        )
        if _:
            return "created"
        if quality.status != AutoDbProductLinkQuality.STATUS_TRUSTED or quality.autodb_supplier_id != int(supplier_id) or quality.autodb_article_number != article_number:
            quality.autodb_supplier_id = int(supplier_id)
            quality.autodb_article_number = article_number
            quality.status = AutoDbProductLinkQuality.STATUS_TRUSTED
            quality.reason = f"safe_apply:{reason}"
            quality.evidence = evidence
            quality.checked_at = timezone.now()
            quality.save(
                update_fields=[
                    "autodb_supplier_id",
                    "autodb_article_number",
                    "status",
                    "reason",
                    "evidence",
                    "checked_at",
                    "updated_at",
                ]
            )
            return "updated"
        return "unchanged"

    def _run_post_link_enrichment(self, *, product: Product) -> dict[str, int | str]:
        supplier_id = int(getattr(product, "autodb_supplier_id", 0) or 0)
        article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
        if supplier_id <= 0 or not article_number:
            return {"status": "failed", "error": "missing_autodb_link"}

        errors: list[str] = []
        name_status = ""
        fitments_created = 0
        fitments_updated = 0
        attributes_created = 0
        attributes_updated = 0
        images_created = 0
        images_stale_marked = 0

        try:
            AutoDbArticleEnrichmentService().enrich_article(
                supplier_id=supplier_id,
                article_number=article_number,
                dry_run=False,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"clone:{exc}")

        try:
            name_result = AutoDbProductNameEnrichmentService().enrich_product(
                product=product,
                dry_run=False,
                only_missing_translations=False,
            )
            name_status = str(name_result.status or "")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"name:{exc}")

        try:
            fitment_result = AutoDbProductFitmentEnrichmentService().enrich_product(product=product, dry_run=False)
            fitments_created = int(fitment_result.fitments_created or 0)
            fitments_updated = int(fitment_result.fitments_updated or 0)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"fitments:{exc}")

        try:
            attribute_result = AutoDbProductAttributeEnrichmentService().enrich_product(product=product, dry_run=False)
            attributes_created = int(attribute_result.product_attributes_created or 0)
            attributes_updated = int(attribute_result.product_attributes_updated or 0)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"attributes:{exc}")

        try:
            image_result = AutoDbProductImageEnrichmentService().sync_product_images(
                product=product,
                dry_run=False,
                prefer_gpl=True,
            )
            images_created = int(image_result.created or 0)
            images_stale_marked = int(image_result.stale_marked or 0)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"images:{exc}")

        status = "ok"
        if errors:
            status = "failed" if len(errors) >= 5 else "partial"
        return {
            "status": status,
            "name_status": name_status,
            "fitments_created": fitments_created,
            "fitments_updated": fitments_updated,
            "attributes_created": attributes_created,
            "attributes_updated": attributes_updated,
            "images_created": images_created,
            "images_stale_marked": images_stale_marked,
            "errors_count": len(errors),
        }
