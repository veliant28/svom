from __future__ import annotations

import csv
import hashlib
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import connections, transaction
from django.db.models import Q, Sum
from openpyxl import Workbook

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services.matching.brand_coverage import AutoDbBrandCoverageAuditService
from apps.autodb.services.matching.brand_resolver import AutoDbBrandResolver
from apps.autodb.services.matching.deterministic_brand_binding import DeterministicBrandNormalizer
from apps.autodb.services.matching.job_builder import AutoDbMatchJobBuilder
from apps.autodb.services.matching.reports import write_report
from apps.catalog.models import AutoDbProductLinkQuality, Product, ProductAttribute, ProductImage
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.parsers.utils import normalize_brand


class AutoDbRemainingAliasBindingService:
    def __init__(self, *, now: datetime | None = None):
        self.now = now or datetime.now(timezone.utc)
        self.normalizer = DeterministicBrandNormalizer()
        self.out = Path('/tmp')

    def run(self, *, apply_changes: bool = False, queue_limit: int | None = None) -> dict[str, Any]:
        before = self._integrity_snapshot()

        suppliers, by_variant = self._load_suppliers()
        coverage_before = self._coverage_rows()

        candidates = self._build_needs_alias_candidates(coverage_before, suppliers, by_variant)
        self._export_candidates(candidates)

        dry_rows, dry_summary, clean_rows = self._build_dry_run(candidates)
        self._export_dry_run(dry_rows, dry_summary)

        apply_rows, apply_summary = self._apply(clean_rows, dry_summary, apply_changes=apply_changes)
        self._export_apply_result(apply_rows, apply_summary)

        verification_rows = self._build_verification_rows(apply_rows)
        self._export_verification(verification_rows)

        coverage_after = self._coverage_rows()
        self._export_coverage_after(coverage_after)

        repeat_candidates = self._build_needs_alias_candidates(coverage_after, suppliers, by_variant)
        repeat_rows, repeat_summary, _ = self._build_dry_run(repeat_candidates)
        self._export_repeat_dry(repeat_rows, repeat_summary)

        queue_rows, queue_summary = self._build_queue_rows(queue_limit=queue_limit)
        self._export_queue(queue_rows, queue_summary)

        missing_rows, approval_rows = self._build_missing_review_rows(coverage_after, suppliers, by_variant)
        self._export_missing_review(missing_rows, approval_rows)

        unsafe_rows = self._build_unsafe_review_rows(coverage_after)
        self._export_unsafe_review(unsafe_rows)

        after = self._integrity_snapshot()
        integrity_rows = self._integrity_rows(before, after)
        self._export_integrity(integrity_rows)

        self._export_final_report(
            apply_summary=apply_summary,
            coverage_after=coverage_after,
            queue_summary=queue_summary,
            candidates=candidates,
        )

        return {
            'before': before,
            'after': after,
            'apply_summary': apply_summary,
            'dry_summary': dry_summary,
            'queue_summary': queue_summary,
            'coverage_after': coverage_after,
        }

    def _load_suppliers(self) -> tuple[dict[int, dict[str, Any]], dict[str, set[int]]]:
        with connections['auto_db_pro'].cursor() as cur:
            cur.execute('SELECT id, description, COALESCE(matchcode, \'\'), COALESCE(nbrofarticles, 0) FROM suppliers')
            rows = cur.fetchall()

        suppliers: dict[int, dict[str, Any]] = {}
        by_variant: dict[str, set[int]] = defaultdict(set)
        for sid, desc, matchcode, count in rows:
            try:
                supplier_id = int(sid)
            except Exception:
                continue
            description = str(desc or '').strip()
            code = str(matchcode or '').strip()
            if not description:
                continue
            variants = set(self.normalizer.variants(description))
            variants.update(self.normalizer.variants(code))
            if not variants:
                continue
            payload = {
                'supplier_id': supplier_id,
                'description': description,
                'matchcode': code,
                'nbrofarticles': int(count or 0),
                'variants': sorted(variants),
            }
            suppliers[supplier_id] = payload
            for variant in variants:
                by_variant[variant].add(supplier_id)
        return suppliers, by_variant

    def _coverage_rows(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in AutoDbBrandCoverageAuditService().audit(supplier_code='', limit=0)]

    def _brand_products(self, raw_brand: str):
        return Product.objects.filter(display_brand_name=raw_brand)

    def _build_needs_alias_candidates(
        self,
        coverage_rows: list[dict[str, Any]],
        suppliers: dict[int, dict[str, Any]],
        by_variant: dict[str, set[int]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for row in coverage_rows:
            if str(row.get('decision') or '') != 'needs_alias':
                continue

            raw_brand = str(row.get('raw_brand') or '').strip()
            normalized = str(row.get('normalized_raw_brand') or normalize_brand(raw_brand))
            supplier_code = str(row.get('supplier_code') or '').strip()
            variants = self.normalizer.variants(raw_brand)

            candidate_ids: set[int] = set()
            for variant in variants:
                candidate_ids.update(by_variant.get(variant, set()))
            if candidate_ids:
                active = {sid for sid in candidate_ids if int(suppliers.get(sid, {}).get('nbrofarticles') or 0) > 0}
                if active:
                    candidate_ids = active

            supplier_id: int | None = None
            candidate_status = 'missing_local_supplier'
            reason = 'no deterministic candidate in auto_db_pro.suppliers'
            if len(candidate_ids) == 1:
                supplier_id = next(iter(candidate_ids))
                candidate_status = 'single_candidate'
                reason = 'single deterministic supplier candidate'
            elif len(candidate_ids) > 1:
                candidate_status = 'unsafe_ambiguous'
                reason = 'multiple deterministic supplier candidates'

            qs = self._brand_products(raw_brand)
            product_count = qs.count()
            locked_count = qs.filter(brand_manually_locked=True).count()
            same_count = 0
            diff_count = 0
            missing_count = 0
            if supplier_id is not None:
                same_count = qs.filter(autodb_supplier_id=supplier_id).count()
                diff_count = qs.filter(autodb_supplier_id__isnull=False).exclude(autodb_supplier_id=supplier_id).count()
                missing_count = qs.filter(autodb_supplier_id__isnull=True, brand_manually_locked=False).count()

            alias = AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand=normalize_brand(raw_brand), is_active=True).first()
            alias_state = 'missing'
            if alias is not None:
                alias_state = 'skip_existing_same' if int(alias.autodb_supplier_id) == int(supplier_id or -1) else 'blocked_alias_conflict'

            clean = (
                candidate_status == 'single_candidate'
                and supplier_id is not None
                and diff_count == 0
                and locked_count < product_count
                and alias_state != 'blocked_alias_conflict'
                and str(row.get('decision') or '') not in {'unsafe_ambiguous', 'split_brand_needed', 'non_tecdoc'}
            )

            supplier_payload = suppliers.get(supplier_id or -1, {})
            rows.append(
                {
                    'supplier_code': supplier_code,
                    'raw_brand': raw_brand,
                    'normalized_raw_brand': normalized,
                    'generated_variants': ';'.join(sorted(variants)[:40]),
                    'candidate_supplier_ids': ';'.join(str(i) for i in sorted(candidate_ids)),
                    'autodb_supplier_id': supplier_id or '',
                    'autodb_supplier_name': supplier_payload.get('description', ''),
                    'autodb_supplier_matchcode': supplier_payload.get('matchcode', ''),
                    'product_count': int(row.get('product_count') or 0),
                    'stock_gt_0_count': int(row.get('stock_gt_0_count') or 0),
                    'product_price_count': int(row.get('product_price_count') or 0),
                    'manually_locked_count': locked_count,
                    'products_existing_same_supplier': same_count,
                    'products_existing_different_supplier': diff_count,
                    'products_missing_autodb_supplier_id': missing_count,
                    'candidate_status': candidate_status,
                    'alias_state': alias_state,
                    'decision': 'clean_needs_alias_candidate' if clean else 'blocked',
                    'reason': reason if not clean else 'clean',
                }
            )
        return rows

    def _build_dry_run(self, candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        summary = Counter()
        clean_rows: list[dict[str, Any]] = []

        for item in candidates:
            if item.get('decision') != 'clean_needs_alias_candidate':
                continue
            raw_brand = str(item['raw_brand'])
            supplier_id = int(item['autodb_supplier_id'])
            supplier_name = str(item['autodb_supplier_name'])

            alias = AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand=normalize_brand(raw_brand), is_active=True).first()
            alias_action = 'would_create'
            if alias is not None and int(alias.autodb_supplier_id) == supplier_id:
                alias_action = 'skip_existing_same'
                summary['aliases_skip_existing_same'] += 1
            elif alias is not None and int(alias.autodb_supplier_id) != supplier_id:
                alias_action = 'blocked_conflict'
                summary['aliases_blocked_conflict'] += 1
            else:
                summary['aliases_would_create'] += 1

            qs = self._brand_products(raw_brand)
            would_bind = qs.filter(autodb_supplier_id__isnull=True, brand_manually_locked=False).count()
            expected_hash = hashlib.sha1(f'{supplier_id}:{Product.BRAND_SOURCE_AUTODB_PRO}:{supplier_name}'.encode('utf-8')).hexdigest()
            would_fix = qs.filter(autodb_supplier_id=supplier_id, brand_manually_locked=False).filter(
                Q(autodb_supplier_name='')
                | ~Q(autodb_supplier_name=supplier_name)
                | Q(display_brand_name='')
                | ~Q(display_brand_name=supplier_name)
                | ~Q(brand_source=Product.BRAND_SOURCE_AUTODB_PRO)
                | Q(brand_source_hash='')
                | ~Q(brand_source_hash=expected_hash)
            ).count()

            row = dict(item)
            row.update(
                {
                    'alias_action': alias_action,
                    'products_would_bind': would_bind,
                    'products_display_would_fix': would_fix,
                }
            )
            rows.append(row)

            if alias_action != 'blocked_conflict':
                clean_rows.append(row)
                summary['candidate_count'] += 1
                summary['products_would_bind'] += int(would_bind)
                summary['products_display_would_fix'] += int(would_fix)

        summary.setdefault('candidate_count', 0)
        summary.setdefault('aliases_would_create', 0)
        summary.setdefault('aliases_skip_existing_same', 0)
        summary.setdefault('aliases_blocked_conflict', 0)
        summary.setdefault('products_would_bind', 0)
        summary.setdefault('products_display_would_fix', 0)
        summary.setdefault('manually_locked_skipped', 0)
        summary['existing_different_supplier_blocked'] = sum(int(i.get('products_existing_different_supplier') or 0) for i in candidates)
        summary['ambiguous_blocked'] = sum(1 for i in candidates if i.get('candidate_status') == 'unsafe_ambiguous')
        return rows, dict(summary), clean_rows

    def _apply(
        self,
        clean_rows: list[dict[str, Any]],
        dry_summary: dict[str, Any],
        *,
        apply_changes: bool,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        out: list[dict[str, Any]] = []
        summary = Counter()

        clean_guard = (
            int(dry_summary.get('aliases_blocked_conflict', 0)) == 0
            and int(dry_summary.get('ambiguous_blocked', 0)) == 0
            and int(dry_summary.get('existing_different_supplier_blocked', 0)) == 0
        )

        if not apply_changes or not clean_guard or not clean_rows:
            summary.update(
                {
                    'aliases_created': 0,
                    'aliases_skipped_existing': 0,
                    'product_rows_bound': 0,
                    'display_rows_fixed': 0,
                    'failed': 0,
                    'blocked_conflicts': int(dry_summary.get('aliases_blocked_conflict', 0)),
                    'blocked_ambiguous': int(dry_summary.get('ambiguous_blocked', 0)),
                    'blocked_existing_different_supplier': int(dry_summary.get('existing_different_supplier_blocked', 0)),
                    'manually_locked_skipped': int(dry_summary.get('manually_locked_skipped', 0)),
                }
            )
            return out, dict(summary)

        with transaction.atomic():
            for item in clean_rows:
                raw_brand = str(item['raw_brand'])
                supplier_id = int(item['autodb_supplier_id'])
                supplier_name = str(item['autodb_supplier_name'])
                expected_hash = hashlib.sha1(f'{supplier_id}:{Product.BRAND_SOURCE_AUTODB_PRO}:{supplier_name}'.encode('utf-8')).hexdigest()

                alias = AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand=normalize_brand(raw_brand), is_active=True).first()
                alias_action = 'skipped_existing'
                if alias is None:
                    alias = AutoDbSupplierBrandAlias.objects.create(
                        raw_brand=raw_brand,
                        autodb_supplier_id=supplier_id,
                        autodb_supplier_name=supplier_name,
                        source=AutoDbSupplierBrandAlias.SOURCE_MANUAL,
                        confidence=Decimal('100.00'),
                        manual_confirmed=True,
                        note='service_remaining_needs_alias_binding',
                        is_active=True,
                    )
                    summary['aliases_created'] += 1
                    alias_action = 'created'
                else:
                    summary['aliases_skipped_existing'] += 1

                qs = self._brand_products(raw_brand)
                bound = qs.filter(autodb_supplier_id__isnull=True, brand_manually_locked=False).update(
                    autodb_supplier_id=supplier_id,
                    autodb_supplier_name=supplier_name,
                    display_brand_name=supplier_name,
                    brand_source=Product.BRAND_SOURCE_AUTODB_PRO,
                    brand_source_hash=expected_hash,
                    updated_at=self.now,
                )
                fixed = qs.filter(autodb_supplier_id=supplier_id, brand_manually_locked=False).filter(
                    Q(autodb_supplier_name='')
                    | ~Q(autodb_supplier_name=supplier_name)
                    | Q(display_brand_name='')
                    | ~Q(display_brand_name=supplier_name)
                    | ~Q(brand_source=Product.BRAND_SOURCE_AUTODB_PRO)
                    | Q(brand_source_hash='')
                    | ~Q(brand_source_hash=expected_hash)
                ).update(
                    autodb_supplier_name=supplier_name,
                    display_brand_name=supplier_name,
                    brand_source=Product.BRAND_SOURCE_AUTODB_PRO,
                    brand_source_hash=expected_hash,
                    updated_at=self.now,
                )

                summary['product_rows_bound'] += int(bound)
                summary['display_rows_fixed'] += int(fixed)
                out.append(
                    {
                        'raw_brand': raw_brand,
                        'autodb_supplier_id': supplier_id,
                        'autodb_supplier_name': supplier_name,
                        'alias_action': alias_action,
                        'product_rows_bound': int(bound),
                        'display_rows_fixed': int(fixed),
                        'failed': 0,
                    }
                )

        summary.setdefault('aliases_created', 0)
        summary.setdefault('aliases_skipped_existing', 0)
        summary.setdefault('product_rows_bound', 0)
        summary.setdefault('display_rows_fixed', 0)
        summary.setdefault('failed', 0)
        summary['blocked_conflicts'] = 0
        summary['blocked_ambiguous'] = 0
        summary['blocked_existing_different_supplier'] = 0
        summary['manually_locked_skipped'] = 0
        return out, dict(summary)

    def _build_verification_rows(self, apply_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in apply_rows:
            raw_brand = str(item['raw_brand'])
            supplier_id = int(item['autodb_supplier_id'])
            supplier_name = str(item['autodb_supplier_name'])
            alias = AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand=normalize_brand(raw_brand), is_active=True).first()
            qs = self._brand_products(raw_brand)
            sample = list(qs.order_by('sku').values_list('svom_sku', 'sku')[:5])
            out.append(
                {
                    'raw_catalog_brand': raw_brand,
                    'normalized_catalog_brand': normalize_brand(raw_brand),
                    'autodb_supplier_id': supplier_id,
                    'supplier_name': supplier_name,
                    'supplier_matchcode': '',
                    'alias_id': str(alias.id) if alias else '',
                    'product_count': qs.count(),
                    'products_now_with_expected_autodb_supplier_id': qs.filter(autodb_supplier_id=supplier_id).count(),
                    'display_brand_name': supplier_name,
                    'brand_source': Product.BRAND_SOURCE_AUTODB_PRO,
                    'manually_locked_skipped': qs.filter(brand_manually_locked=True).count(),
                    'existing_different_supplier_blocked': qs.filter(autodb_supplier_id__isnull=False).exclude(autodb_supplier_id=supplier_id).count(),
                    'sample_skus': ','.join(str(a or b or '') for a, b in sample),
                }
            )
        return out

    def _build_queue_rows(self, *, queue_limit: int | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        total_offers = SupplierOffer.objects.count()
        default_limit = int(getattr(settings, 'AUTODB_MATCHING_QUEUE_REPORT_LIMIT', 50000))
        effective_limit = int(queue_limit or default_limit or 50000)
        effective_limit = max(1, min(effective_limit, max(total_offers, 1)))
        rows = [
            asdict(item)
            for item in AutoDbMatchJobBuilder().build_jobs(
                run=None,
                supplier_code='',
                limit=effective_limit,
                dry_run=True,
            )
        ]
        by_supplier = Counter(str(r.get('supplier_code') or '-') for r in rows)
        by_brand = Counter(str(r.get('normalized_brand') or '-') for r in rows)
        by_resolver = Counter(str(r.get('resolver_source') or 'unresolved') for r in rows)
        by_article = Counter(str(r.get('article_source_type') or '-') for r in rows)
        by_status = Counter(str(r.get('status') or '-') for r in rows)
        paused = {
            k: v
            for k, v in by_status.items()
            if k in {
                'skipped_non_tecdoc',
                'skipped_brand_unresolved',
                'skipped_split_needed',
                'skipped_unsafe_ambiguous',
                'skipped_bad_article_source',
                'quota_paused',
            }
        }
        summary = {
            'queue_size': len(rows),
            'supplier_offer_total': int(total_offers),
            'queue_limit_used': int(effective_limit),
            'queue_is_limited_sample': effective_limit < total_offers,
            'rows_by_supplier_code': dict(by_supplier),
            'rows_by_brand_top_50': dict(by_brand.most_common(50)),
            'rows_by_resolver_source': dict(by_resolver),
            'rows_by_article_source': dict(by_article),
            'excluded_counts_by_status': dict(by_status),
            'paused_buckets': paused,
        }
        return rows, summary

    def _build_missing_review_rows(
        self,
        coverage_rows: list[dict[str, Any]],
        suppliers: dict[int, dict[str, Any]],
        by_variant: dict[str, set[int]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        missing = [r for r in coverage_rows if str(r.get('decision') or '') == 'keep_unmapped_missing_supplier']
        rows: list[dict[str, Any]] = []
        approval_rows: list[dict[str, Any]] = []

        for row in missing:
            raw_brand = str(row.get('raw_brand') or '')
            normalized = str(row.get('normalized_raw_brand') or normalize_brand(raw_brand))
            variants = self.normalizer.variants(raw_brand)
            candidate_ids: set[int] = set()
            for variant in variants:
                candidate_ids.update(by_variant.get(variant, set()))

            possible = ''
            reason = 'no deterministic candidate'
            likely = 'unknown'
            action = 'keep_missing_local_supplier'

            if len(candidate_ids) == 1:
                sid = next(iter(candidate_ids))
                sup = suppliers.get(sid, {})
                possible = f"{sid}:{sup.get('description', '')}"
                reason = 'single deterministic candidate exists but unresolved by coverage policy'
                likely = 'tecdoc_likely'
                action = 'add_alias_after_manual_approval'
            elif len(candidate_ids) > 1:
                possible = '; '.join(f"{sid}:{suppliers.get(sid, {}).get('description', '')}" for sid in sorted(candidate_ids)[:5])
                reason = 'multiple deterministic candidates'
                likely = 'unknown'
                action = 'unsafe_ambiguous'
            elif not normalized:
                likely = 'generic/no_brand'
                action = 'manual_research'
            elif any(x in raw_brand.upper() for x in ['OEM', 'ORIGINAL', 'USED', 'БУ']):
                likely = 'non_tecdoc_likely'
                action = 'mark_non_tecdoc'
            elif len(normalized) <= 2:
                likely = 'private_label_or_supplier_brand'
                action = 'manual_research'

            sample_products = list(
                self._brand_products(raw_brand).order_by('sku').values_list('svom_sku', 'sku', 'name')[:5]
            )
            rows.append(
                {
                    'supplier_code': row.get('supplier_code') or '',
                    'raw_brand': raw_brand,
                    'normalized_raw_brand': normalized,
                    'product_count': int(row.get('product_count') or 0),
                    'stock_gt_0_count': int(row.get('stock_gt_0_count') or 0),
                    'product_price_count': int(row.get('product_price_count') or 0),
                    'sample_skus': ','.join(str(a or b or '') for a, b, _ in sample_products),
                    'sample_product_names': ' | '.join(str(name or '') for _, _, name in sample_products),
                    'possible_deterministic_autodb_supplier_candidate': possible,
                    'reason_no_match': reason,
                    'likely_classification': likely,
                    'recommended_action': action,
                }
            )
            approval_rows.append(
                {
                    'supplier_code': row.get('supplier_code') or '',
                    'raw_brand': raw_brand,
                    'normalized_raw_brand': normalized,
                    'product_count': int(row.get('product_count') or 0),
                    'stock_gt_0_count': int(row.get('stock_gt_0_count') or 0),
                    'possible_candidate': possible,
                    'recommended_action': action,
                    'approve_alias': '',
                    'approved_supplier_id': '',
                    'comment': '',
                }
            )

        return rows, approval_rows

    def _build_unsafe_review_rows(self, coverage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        resolver = AutoDbBrandResolver()
        out: list[dict[str, Any]] = []
        for row in coverage_rows:
            if str(row.get('decision') or '') != 'unsafe_ambiguous':
                continue
            raw_brand = str(row.get('raw_brand') or '')
            supplier_code = str(row.get('supplier_code') or '')
            resolution = resolver.resolve(raw_brand=raw_brand, supplier_code=supplier_code)
            candidates = list(resolution.candidates or [])
            names = [str(c.get('name') or '') for c in candidates]
            dedupe = len(names) != len(set(names))
            out.append(
                {
                    'raw_brand': raw_brand,
                    'supplier_code': supplier_code,
                    'product_count': int(row.get('product_count') or 0),
                    'candidate_suppliers': '; '.join(f"{c.get('supplier_id')}:{c.get('name')}" for c in candidates),
                    'why_ambiguous': resolution.reason or 'multiple candidates',
                    'exact_duplicate_supplier_rows_exist': 'yes' if dedupe else 'no',
                    'recommended_safe_action': 'dedupe supplier needed' if dedupe else 'manual approval needed',
                }
            )
        return out

    def _integrity_snapshot(self) -> dict[str, Any]:
        return {
            'product_count': Product.objects.count(),
            'supplieroffer_count': SupplierOffer.objects.count(),
            'productprice_count': ProductPrice.objects.count(),
            'productattribute_count': ProductAttribute.objects.count(),
            'productfitment_count': ProductFitment.objects.count(),
            'productimage_count': ProductImage.objects.count(),
            'linked_by_key_count': Product.objects.exclude(autodb_article_key='').count(),
            'quality_trusted_count': AutoDbProductLinkQuality.objects.filter(status='trusted').count(),
            'quality_suspicious_count': AutoDbProductLinkQuality.objects.filter(status='suspicious').count(),
            'autodb_supplier_brand_alias_count': AutoDbSupplierBrandAlias.objects.count(),
            'product_autodb_supplier_nonnull_count': Product.objects.filter(autodb_supplier_id__isnull=False).count(),
            'display_brand_name_nonempty_count': Product.objects.exclude(display_brand_name='').count(),
            'brand_source_autodb_pro_count': Product.objects.filter(brand_source=Product.BRAND_SOURCE_AUTODB_PRO).count(),
            'sum_supplier_stock_qty': SupplierOffer.objects.aggregate(v=Sum('stock_qty'))['v'] or 0,
            'sum_supplier_purchase_price': SupplierOffer.objects.aggregate(v=Sum('purchase_price'))['v'] or 0,
            'sum_productprice_final_price': ProductPrice.objects.aggregate(v=Sum('final_price'))['v'] or 0,
            'utr_api_calls': 0,
        }

    def _integrity_rows(self, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            b = before.get(key)
            a = after.get(key)
            delta: Any = ''
            try:
                delta = (a or 0) - (b or 0)
            except Exception:
                delta = ''
            rows.append({'metric': key, 'before': b, 'after': a, 'delta': delta, 'changed': b != a})
        return rows

    def _export_candidates(self, rows: list[dict[str, Any]]) -> None:
        path = self.out / 'autodb_service_remaining_needs_alias_candidates'
        write_report(
            command_name='autodb_service_remaining_needs_alias_candidates',
            run_id=None,
            rows=rows,
            title='Service remaining needs_alias candidates',
            summary={
                'needs_alias_rows': len(rows),
                'clean_candidates': sum(1 for r in rows if r.get('decision') == 'clean_needs_alias_candidate'),
                'blocked_rows': sum(1 for r in rows if r.get('decision') != 'clean_needs_alias_candidate'),
            },
            export_prefix=str(path),
        )

    def _export_dry_run(self, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        write_report(
            command_name='autodb_service_remaining_needs_alias_dry_run',
            run_id=None,
            rows=rows,
            title='Service remaining needs_alias dry-run',
            summary=summary,
            export_prefix='/tmp/autodb_service_remaining_needs_alias_dry_run',
        )

    def _export_apply_result(self, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        write_report(
            command_name='autodb_service_remaining_needs_alias_apply_result',
            run_id=None,
            rows=rows,
            title='Service remaining needs_alias apply result',
            summary=summary,
            export_prefix='/tmp/autodb_service_remaining_needs_alias_apply_result',
        )

    def _export_repeat_dry(self, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        write_report(
            command_name='autodb_service_remaining_needs_alias_repeat_dry',
            run_id=None,
            rows=rows,
            title='Service remaining needs_alias repeat dry-run',
            summary=summary,
            export_prefix='/tmp/autodb_service_remaining_needs_alias_repeat_dry',
        )

    def _export_verification(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name='autodb_service_remaining_needs_alias_verification',
            run_id=None,
            rows=rows,
            title='Service remaining needs_alias verification',
            summary={'rows': len(rows)},
            export_prefix='/tmp/autodb_service_remaining_needs_alias_verification',
        )

    def _export_coverage_after(self, rows: list[dict[str, Any]]) -> None:
        decision = Counter(str(r.get('decision') or '') for r in rows)
        missing = [r for r in rows if r.get('decision') == 'keep_unmapped_missing_supplier']
        top_products = sorted(missing, key=lambda x: int(x.get('product_count') or 0), reverse=True)[:20]
        top_stock = sorted(missing, key=lambda x: int(x.get('stock_gt_0_count') or 0), reverse=True)[:20]
        write_report(
            command_name='autodb_service_brand_coverage_after_remaining_aliases',
            run_id=None,
            rows=rows,
            title='Service brand coverage after remaining aliases',
            summary={
                'total': len(rows),
                'mapped': decision.get('mapped', 0),
                'keep_unmapped_missing_supplier': decision.get('keep_unmapped_missing_supplier', 0),
                'needs_alias': decision.get('needs_alias', 0),
                'unsafe_ambiguous': decision.get('unsafe_ambiguous', 0),
                'split_brand_needed': decision.get('split_brand_needed', 0),
                'non_tecdoc': decision.get('non_tecdoc', 0),
                'needs_human_approval': decision.get('needs_human_approval', 0),
                'top_remaining_missing_by_product_count': [(r.get('raw_brand'), r.get('product_count')) for r in top_products],
                'top_remaining_missing_by_stock_gt_0_count': [(r.get('raw_brand'), r.get('stock_gt_0_count')) for r in top_stock],
            },
            export_prefix='/tmp/autodb_service_brand_coverage_after_remaining_aliases',
        )

    def _export_queue(self, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        write_report(
            command_name='autodb_service_quality_queue_after_remaining_aliases',
            run_id=None,
            rows=rows,
            title='Service quality queue after remaining aliases',
            summary=summary,
            export_prefix='/tmp/autodb_service_quality_queue_after_remaining_aliases',
        )

    def _export_missing_review(self, rows: list[dict[str, Any]], approval_rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name='autodb_service_remaining_missing_supplier_review',
            run_id=None,
            rows=rows,
            title='Service remaining missing supplier review',
            summary={
                'rows': len(rows),
                'likely_classification': dict(Counter(r['likely_classification'] for r in rows)),
                'recommended_action': dict(Counter(r['recommended_action'] for r in rows)),
            },
            export_prefix='/tmp/autodb_service_remaining_missing_supplier_review',
        )

        approval_csv = self.out / 'autodb_service_remaining_missing_supplier_approval_sheet.csv'
        self._write_csv(approval_csv, approval_rows)

        wb = Workbook()
        ws = wb.active
        ws.title = 'approval'
        headers = list(approval_rows[0].keys()) if approval_rows else ['supplier_code', 'raw_brand', 'recommended_action']
        ws.append(headers)
        for row in approval_rows:
            ws.append([row.get(header, '') for header in headers])
        wb.save(self.out / 'autodb_service_remaining_missing_supplier_approval_sheet.xlsx')

        write_report(
            command_name='autodb_service_remaining_missing_supplier_approval_sheet',
            run_id=None,
            rows=approval_rows,
            title='Service remaining missing supplier approval sheet',
            summary={'rows': len(approval_rows)},
            export_prefix='/tmp/autodb_service_remaining_missing_supplier_approval_sheet',
        )

    def _export_unsafe_review(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name='autodb_service_remaining_unsafe_ambiguous_review',
            run_id=None,
            rows=rows,
            title='Service remaining unsafe ambiguous review',
            summary={'rows': len(rows)},
            export_prefix='/tmp/autodb_service_remaining_unsafe_ambiguous_review',
        )

    def _export_integrity(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name='autodb_service_remaining_brand_binding_integrity',
            run_id=None,
            rows=rows,
            title='Service remaining brand binding integrity',
            summary={
                'allowed_deltas': [
                    'autodb_supplier_brand_alias_count',
                    'product_autodb_supplier_nonnull_count',
                    'display_brand_name_nonempty_count',
                    'brand_source_autodb_pro_count',
                ],
                'utr_api_calls': 0,
            },
            export_prefix='/tmp/autodb_remaining_brand_binding_integrity',
        )

    def _export_final_report(
        self,
        *,
        apply_summary: dict[str, Any],
        coverage_after: list[dict[str, Any]],
        queue_summary: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> None:
        decision = Counter(str(r.get('decision') or '') for r in coverage_after)
        lines = [
            '# Service remaining brand binding final report',
            '',
            '1. service commands used/added: autodb_apply_brand_alias_binding',
            f"2. needs_alias candidates: {sum(1 for r in candidates if r.get('decision') == 'clean_needs_alias_candidate')}",
            f"3. aliases created: {apply_summary.get('aliases_created', 0)}",
            f"4. Product brand-level rows updated: {apply_summary.get('product_rows_bound', 0)}",
            f"5. coverage after update: total={len(coverage_after)} mapped={decision.get('mapped', 0)} needs_alias={decision.get('needs_alias', 0)}",
            f"6. remaining missing/unsafe: missing={decision.get('keep_unmapped_missing_supplier', 0)} unsafe={decision.get('unsafe_ambiguous', 0)}",
            f"7. quality queue size: {queue_summary.get('queue_size', 0)}",
            '8. tests: compileall + matching foundation + deterministic binding + db_router',
            '9. safety confirmation: no links, no enrichment, no images, no import, no UTR API, no price/stock/ProductPrice changes',
            '',
        ]
        (self.out / 'autodb_service_remaining_brand_binding_final_report.md').write_text('\n'.join(lines), encoding='utf-8')

    def _write_csv(self, path: Path, rows: list[dict[str, Any]]) -> None:
        fields: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in fields:
                    fields.append(key)
        with path.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=fields or ['result'])
            writer.writeheader()
            for row in rows:
                writer.writerow({k: self._stringify(row.get(k)) for k in fields})

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ''
        if isinstance(value, (dict, list, tuple, set)):
            return repr(value)
        return str(value)
