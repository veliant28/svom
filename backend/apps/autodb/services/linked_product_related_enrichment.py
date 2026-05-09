from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

from django.utils import timezone
from django.db.models import F, QuerySet

from apps.autodb.models import AutoDbSyncState
from apps.autodb.services.article_enrichment import AutoDbArticleEnrichmentService
from apps.autodb.services.column_helpers import find_column_name
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.compatibility.models import ProductFitment


@dataclass(frozen=True)
class LinkedProductRelatedLocalState:
    article_exists: bool
    article_prd_rows: int
    article_links_rows: int
    prd_rows: int

    @property
    def related_found_local(self) -> bool:
        return (self.article_prd_rows > 0 or self.article_links_rows > 0) and self.prd_rows > 0


@dataclass(frozen=True)
class LinkedRelatedStateSnapshot:
    state_key: str
    source_table: str
    status: str
    last_offset: int
    last_cursor: str
    metadata: dict
    remote_queries_used: int


class AutoDbLinkedProductRelatedEnrichmentService:
    def __init__(
        self,
        *,
        storage: AutoDbRawCloneStorage | None = None,
        article_enrichment: AutoDbArticleEnrichmentService | None = None,
    ):
        self.storage = storage or AutoDbRawCloneStorage()
        self.article_enrichment = article_enrichment or AutoDbArticleEnrichmentService(storage=self.storage)

    def build_queryset(self, *, only_linked: bool, only_trusted: bool, product_id: str) -> QuerySet[Product]:
        qs = Product.objects.select_related("category").order_by("id")
        if only_linked:
            qs = qs.filter(autodb_supplier_id__isnull=False).exclude(autodb_article_number="")
        if only_trusted:
            qs = qs.filter(
                autodb_link_qualities__status=AutoDbProductLinkQuality.STATUS_TRUSTED,
                autodb_link_qualities__autodb_article_key=F("autodb_article_key"),
            )
        if product_id:
            qs = qs.filter(pk=product_id)
        return qs.distinct()

    def inspect_local_state(self, *, supplier_id: int | None, article_number: str) -> LinkedProductRelatedLocalState:
        if supplier_id is None or supplier_id <= 0 or not article_number:
            return LinkedProductRelatedLocalState(
                article_exists=False,
                article_prd_rows=0,
                article_links_rows=0,
                prd_rows=0,
            )

        article_exists = self._count_rows(
            table="articles",
            supplier_id=supplier_id,
            article_number=article_number,
            limit=1,
        ) > 0
        article_prd_rows = self._count_rows(
            table="article_prd",
            supplier_id=supplier_id,
            article_number=article_number,
            limit=2000,
        )
        article_links_rows = self._count_rows(
            table="article_links",
            supplier_id=supplier_id,
            article_number=article_number,
            limit=2000,
        )
        prd_rows = self._count_prd_rows_for_article(
            supplier_id=supplier_id,
            article_number=article_number,
            limit=4000,
        )
        return LinkedProductRelatedLocalState(
            article_exists=article_exists,
            article_prd_rows=article_prd_rows,
            article_links_rows=article_links_rows,
            prd_rows=prd_rows,
        )

    def is_suspicious_for_related_enrichment(self, *, product: Product) -> bool:
        article_key = str(getattr(product, "autodb_article_key", "") or "").strip()
        if not article_key:
            return False

        quality = (
            AutoDbProductLinkQuality.objects.filter(
                product=product,
                autodb_article_key=article_key,
            )
            .order_by("-checked_at", "-updated_at")
            .first()
        )
        if quality is not None and str(quality.status or "") in {
            AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
        }:
            return True

        return ProductFitment.objects.filter(
            product=product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_article_key=article_key,
            excluded_from_public_filtering=True,
        ).exists()

    def enrich_related(
        self,
        *,
        supplier_id: int | None,
        article_number: str,
        tables: list[str],
        dry_run: bool,
        allow_remote: bool,
    ):
        if not allow_remote:
            return None
        return self.article_enrichment.enrich_article(
            supplier_id=supplier_id,
            article_number=article_number,
            tables=tables,
            dry_run=dry_run,
        )

    def _count_rows(
        self,
        *,
        table: str,
        supplier_id: int,
        article_number: str,
        limit: int,
    ) -> int:
        self.storage.ensure_table(table)
        columns = list(self.storage.get_local_columns(table))
        if not columns:
            return 0
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            [
                "DataSupplierArticleNumber",
                "datasupplierarticlenumber",
                "PartsDataSupplierArticleNumber",
                "partsdatasupplierarticlenumber",
                "article",
                "articlenumber",
                "number",
            ],
        )
        if not supplier_column or not article_column:
            return 0
        rows = self.storage.fetch_local_rows(
            table=table,
            filters={
                supplier_column: supplier_id,
                article_column: article_number,
            },
            limit=limit,
            columns=[supplier_column, article_column],
        )
        return len(rows)

    def _count_prd_rows_for_article(self, *, supplier_id: int, article_number: str, limit: int) -> int:
        product_ids = self._collect_related_product_ids(
            table="article_prd",
            supplier_id=supplier_id,
            article_number=article_number,
            product_candidates=["productId", "productid", "ProductId", "prdid", "prdId", "id"],
        )
        product_ids |= self._collect_related_product_ids(
            table="article_links",
            supplier_id=supplier_id,
            article_number=article_number,
            product_candidates=["productId", "productid", "ProductId", "prdid", "prdId", "id"],
        )
        if not product_ids:
            return 0

        self.storage.ensure_table("prd")
        columns = list(self.storage.get_local_columns("prd"))
        if not columns:
            return 0
        id_column = find_column_name(columns, ["id", "productId", "productid", "ProductId", "prdid", "prdId"])
        if not id_column:
            return 0
        rows = self.storage.fetch_local_rows_in(
            table="prd",
            column=id_column,
            values=sorted(product_ids),
            limit=limit,
            columns=[id_column],
        )
        return len(rows)

    def _collect_related_product_ids(
        self,
        *,
        table: str,
        supplier_id: int,
        article_number: str,
        product_candidates: list[str],
    ) -> set[int]:
        self.storage.ensure_table(table)
        columns = list(self.storage.get_local_columns(table))
        if not columns:
            return set()
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            [
                "DataSupplierArticleNumber",
                "datasupplierarticlenumber",
                "PartsDataSupplierArticleNumber",
                "partsdatasupplierarticlenumber",
                "article",
                "articlenumber",
                "number",
            ],
        )
        product_column = find_column_name(columns, product_candidates)
        if not supplier_column or not article_column or not product_column:
            return set()
        rows = self.storage.fetch_local_rows(
            table=table,
            filters={
                supplier_column: supplier_id,
                article_column: article_number,
            },
            limit=2000,
            columns=[product_column],
        )
        out: set[int] = set()
        for row in rows:
            try:
                value = int(row.get(product_column))
            except (TypeError, ValueError):
                continue
            out.add(value)
        return out


def extract_related_tables(raw_tables: Iterable[str]) -> list[str]:
    requested = [str(item or "").strip() for item in raw_tables]
    out: list[str] = []
    for table in requested:
        if table and table not in out:
            out.append(table)
    return out


def estimate_remote_queries_for_tables(tables: list[str]) -> int:
    requested = [str(item or "").strip() for item in tables]
    if not requested:
        return 0
    queries = sum(1 for table in requested if table and table != "prd")
    if "prd" in requested:
        queries += 1
    return queries


def is_related_local_complete(*, state: LinkedProductRelatedLocalState, tables: list[str]) -> bool:
    for table in tables:
        name = str(table or "").strip()
        if name == "article_prd" and state.article_prd_rows <= 0:
            return False
        elif name == "article_links" and state.article_links_rows <= 0:
            return False
        elif name == "prd" and state.prd_rows <= 0:
            return False
        elif name == "articles" and not state.article_exists:
            return False
        elif name not in {"article_prd", "article_links", "prd", "articles"}:
            return False
    return True


def is_remote_quota_error(message: str) -> bool:
    normalized = str(message or "").strip().lower()
    if not normalized:
        return False
    return (
        "1226" in normalized
        or "max_questions" in normalized
        or "user has exceeded the 'max_questions'" in normalized
        or "has exceeded the 'max_questions'" in normalized
    )


class LinkedProductRelatedStateStore:
    SOURCE_TABLE_PREFIX = "linked_related:"
    DB_ALIAS = "auto_db_pro"

    def load(self, *, state_key: str) -> LinkedRelatedStateSnapshot | None:
        state = AutoDbSyncState.objects.using(self.DB_ALIAS).filter(source_table=self._source_table(state_key)).first()
        if state is None:
            return None
        return self._snapshot(state=state, state_key=state_key)

    def reset(self, *, state_key: str) -> LinkedRelatedStateSnapshot:
        state = self._get_or_create(state_key=state_key)
        state.status = AutoDbSyncState.Status.PENDING
        state.last_pk = None
        state.last_offset = 0
        state.last_cursor = ""
        state.total_rows = 0
        state.processed_rows = 0
        state.failed_rows = 0
        state.started_at = None
        state.finished_at = None
        state.last_error = ""
        state.metadata = {}
        state.save(
            using=self.DB_ALIAS,
            update_fields=[
                "status",
                "last_pk",
                "last_offset",
                "last_cursor",
                "total_rows",
                "processed_rows",
                "failed_rows",
                "started_at",
                "finished_at",
                "last_error",
                "metadata",
                "updated_at",
            ],
        )
        return self._snapshot(state=state, state_key=state_key)

    def mark_running(
        self,
        *,
        state_key: str,
        total_rows: int,
        metadata: dict,
        resume: bool,
    ) -> LinkedRelatedStateSnapshot:
        state = self._get_or_create(state_key=state_key)
        now = timezone.now()
        state.status = AutoDbSyncState.Status.RUNNING
        if not resume:
            state.last_pk = None
            state.last_offset = 0
            state.last_cursor = ""
            state.processed_rows = 0
            state.failed_rows = 0
            state.last_error = ""
        state.total_rows = max(int(total_rows), 0)
        state.started_at = state.started_at or now
        state.finished_at = None
        state.metadata = dict(metadata or {})
        state.save(
            using=self.DB_ALIAS,
            update_fields=[
                "status",
                "last_pk",
                "last_offset",
                "last_cursor",
                "processed_rows",
                "failed_rows",
                "last_error",
                "total_rows",
                "started_at",
                "finished_at",
                "metadata",
                "updated_at",
            ],
        )
        return self._snapshot(state=state, state_key=state_key)

    def save_progress(
        self,
        *,
        state_key: str,
        processed_rows: int,
        failed_rows: int,
        last_offset: int,
        last_cursor: str,
        metadata_patch: dict | None = None,
    ) -> LinkedRelatedStateSnapshot:
        state = self._get_or_create(state_key=state_key)
        state.processed_rows = max(int(processed_rows), 0)
        state.failed_rows = max(int(failed_rows), 0)
        state.last_offset = max(int(last_offset), 0)
        state.last_cursor = str(last_cursor or "")[:255]
        merged = dict(state.metadata or {})
        if metadata_patch:
            merged.update(dict(metadata_patch))
        state.metadata = merged
        state.save(
            using=self.DB_ALIAS,
            update_fields=[
                "processed_rows",
                "failed_rows",
                "last_offset",
                "last_cursor",
                "metadata",
                "updated_at",
            ],
        )
        return self._snapshot(state=state, state_key=state_key)

    def finish(
        self,
        *,
        state_key: str,
        status: str,
        error: str,
        metadata_patch: dict | None = None,
    ) -> LinkedRelatedStateSnapshot:
        state = self._get_or_create(state_key=state_key)
        state.status = status
        state.finished_at = timezone.now()
        state.last_error = str(error or "")[:4000]
        merged = dict(state.metadata or {})
        if metadata_patch:
            merged.update(dict(metadata_patch))
        state.metadata = merged
        state.save(
            using=self.DB_ALIAS,
            update_fields=[
                "status",
                "finished_at",
                "last_error",
                "metadata",
                "updated_at",
            ],
        )
        return self._snapshot(state=state, state_key=state_key)

    def _get_or_create(self, *, state_key: str) -> AutoDbSyncState:
        source_table = self._source_table(state_key)
        state, _ = AutoDbSyncState.objects.using(self.DB_ALIAS).get_or_create(source_table=source_table)
        return state

    def _snapshot(self, *, state: AutoDbSyncState, state_key: str) -> LinkedRelatedStateSnapshot:
        metadata = dict(state.metadata or {})
        remote_queries_used = int(metadata.get("remote_queries_used", 0) or 0)
        return LinkedRelatedStateSnapshot(
            state_key=state_key,
            source_table=str(state.source_table or ""),
            status=str(state.status or ""),
            last_offset=int(state.last_offset or 0),
            last_cursor=str(state.last_cursor or ""),
            metadata=metadata,
            remote_queries_used=remote_queries_used,
        )

    def _source_table(self, state_key: str) -> str:
        raw_key = str(state_key or "").strip() or "default"
        full = f"{self.SOURCE_TABLE_PREFIX}{raw_key}"
        if len(full) <= 64:
            return full
        digest = hashlib.sha1(raw_key.encode("utf-8")).hexdigest()[:12]
        prefix = self.SOURCE_TABLE_PREFIX[:50]
        return f"{prefix}{digest}"
