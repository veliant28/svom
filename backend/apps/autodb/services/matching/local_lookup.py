from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob, AutoDbMatchingRun
from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.column_helpers import find_column_name
from apps.autodb.services.matching.constants import DETERMINISTIC_TABLES
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage


@dataclass(frozen=True)
class AutoDbLocalLookupResult:
    job_id: str
    status: str
    supplier_id: int | None
    canonical_article: str
    remote_stored_article: str
    matched_table: str
    local_hits: int
    article_prd_rows: int
    prd_rows: int
    article_prd_present: bool
    prd_present: bool
    reason: str


class AutoDbLocalLookupService:
    def __init__(
        self,
        *,
        storage: AutoDbRawCloneStorage | None = None,
        normalizer: ArticleNumberNormalizer | None = None,
    ):
        self.storage = storage or AutoDbRawCloneStorage()
        self.normalizer = normalizer or ArticleNumberNormalizer()

    def lookup_job(
        self,
        job: AutoDbMatchJob,
        *,
        run: AutoDbMatchingRun | None = None,
        dry_run: bool = True,
    ) -> AutoDbLocalLookupResult:
        del dry_run
        supplier_id = int(job.resolved_supplier_id) if job.resolved_supplier_id is not None else None
        canonical = str(job.canonical_article or "").strip()
        if supplier_id is None or not canonical:
            return self._finish(
                job=job,
                run=run,
                status=AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE,
                supplier_id=supplier_id,
                canonical_article=canonical,
                remote_stored_article="",
                matched_table="",
                local_hits=0,
                article_prd_rows=0,
                prd_rows=0,
                reason="missing supplier_id or canonical_article",
            )

        hit_table, stored_article, local_hits = self._lookup_article(supplier_id=supplier_id, canonical_article=canonical)
        if not hit_table:
            return self._finish(
                job=job,
                run=run,
                status=AutoDbMatchJob.STATUS_REMOTE_PENDING,
                supplier_id=supplier_id,
                canonical_article=canonical,
                remote_stored_article="",
                matched_table="",
                local_hits=0,
                article_prd_rows=0,
                prd_rows=0,
                reason="local deterministic article not found",
            )

        article_prd_rows, prd_rows = self._read_local_linkage(supplier_id=supplier_id, article_number=stored_article or canonical)
        if article_prd_rows <= 0 or prd_rows <= 0:
            return self._finish(
                job=job,
                run=run,
                status=AutoDbMatchJob.STATUS_REMOTE_PENDING,
                supplier_id=supplier_id,
                canonical_article=canonical,
                remote_stored_article=stored_article,
                matched_table=hit_table,
                local_hits=local_hits,
                article_prd_rows=article_prd_rows,
                prd_rows=prd_rows,
                reason="local article found but article_prd/prd linkage missing",
            )

        return self._finish(
            job=job,
            run=run,
            status=AutoDbMatchJob.STATUS_LOCAL_FOUND,
            supplier_id=supplier_id,
            canonical_article=canonical,
            remote_stored_article=stored_article,
            matched_table=hit_table,
            local_hits=local_hits,
            article_prd_rows=article_prd_rows,
            prd_rows=prd_rows,
            reason="local deterministic lookup found linked article",
        )

    def _lookup_article(self, *, supplier_id: int, canonical_article: str) -> tuple[str, str, int]:
        variants = self._variants(canonical_article)
        total_hits = 0
        for table in DETERMINISTIC_TABLES:
            columns = self.storage.get_local_columns(table)
            supplier_col, article_col = self._supplier_article_columns(columns)
            if not supplier_col or not article_col:
                continue
            for variant in variants[:8]:
                rows = self.storage.fetch_local_rows(
                    table=table,
                    filters={supplier_col: supplier_id, article_col: variant},
                    columns=[article_col],
                    limit=5,
                )
                if rows:
                    total_hits += len(rows)
                    return table, str(rows[0].get(article_col) or variant).strip(), total_hits
        return "", "", total_hits

    def _read_local_linkage(self, *, supplier_id: int, article_number: str) -> tuple[int, int]:
        article_prd_columns = self.storage.get_local_columns("article_prd")
        supplier_col, article_col = self._supplier_article_columns(article_prd_columns)
        product_col = find_column_name(article_prd_columns, ["productId", "productid", "ProductId", "prdId", "prdid", "id"])
        if not supplier_col or not article_col or not product_col:
            return 0, 0

        rows = self.storage.fetch_local_rows(
            table="article_prd",
            filters={supplier_col: supplier_id, article_col: article_number},
            columns=[product_col],
            limit=5000,
        )
        product_ids = [row.get(product_col) for row in rows if row.get(product_col) not in (None, "")]
        if not product_ids:
            return len(rows), 0

        prd_columns = self.storage.get_local_columns("prd")
        prd_id_col = find_column_name(prd_columns, ["id", "productId", "productid", "ProductId", "prdId", "prdid"])
        if not prd_id_col:
            return len(rows), 0
        prd_rows = self.storage.fetch_local_rows_in(
            table="prd",
            column=prd_id_col,
            values=product_ids,
            columns=[prd_id_col],
            limit=max(len(product_ids) * 2, 100),
        )
        return len(rows), len(prd_rows)

    def _finish(
        self,
        *,
        job: AutoDbMatchJob,
        run: AutoDbMatchingRun | None,
        status: str,
        supplier_id: int | None,
        canonical_article: str,
        remote_stored_article: str,
        matched_table: str,
        local_hits: int,
        article_prd_rows: int,
        prd_rows: int,
        reason: str,
    ) -> AutoDbLocalLookupResult:
        job.status = status
        job.last_run = run
        job.last_error = "" if status == AutoDbMatchJob.STATUS_LOCAL_FOUND else reason
        job.save(update_fields=["status", "last_run", "last_error", "updated_at"])
        AutoDbMatchEvidence.objects.create(
            job=job,
            stage="local_lookup",
            source="local_clone",
            result=status,
            supplier_id=supplier_id,
            article_value=job.article_value,
            canonical_article=canonical_article,
            remote_stored_article=remote_stored_article,
            article_prd_present=article_prd_rows > 0,
            prd_present=prd_rows > 0,
            reason=reason,
            payload_json={
                "matched_table": matched_table,
                "local_hits": local_hits,
                "article_prd_rows": article_prd_rows,
                "prd_rows": prd_rows,
            },
        )
        return AutoDbLocalLookupResult(
            job_id=str(job.id),
            status=status,
            supplier_id=supplier_id,
            canonical_article=canonical_article,
            remote_stored_article=remote_stored_article,
            matched_table=matched_table,
            local_hits=local_hits,
            article_prd_rows=article_prd_rows,
            prd_rows=prd_rows,
            article_prd_present=article_prd_rows > 0,
            prd_present=prd_rows > 0,
            reason=reason,
        )

    def _variants(self, canonical_article: str) -> list[str]:
        normalized = self.normalizer.normalize(canonical_article)
        variants = list(normalized.search_variants)
        if canonical_article and canonical_article not in variants:
            variants.append(canonical_article)
        if normalized.normalized and normalized.normalized not in variants:
            variants.append(normalized.normalized)
        return variants

    def _supplier_article_columns(self, columns: set[str]) -> tuple[str | None, str | None]:
        supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id", "supplier"])
        article_col = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articleNumber", "articlenumber", "article", "number"],
        )
        return supplier_col, article_col
