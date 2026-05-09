from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.autodb.models import AutoDbSupplierBrandAlias, AutoDbSyncState
from apps.autodb.services import is_remote_quota_error
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.remote_client import AutoDbProRemoteClientError
from apps.catalog.models import Product
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


@dataclass
class PairCandidate:
    raw_brand: str
    td_article: str
    gpl_article: str
    lookup_article: str
    supplier_id: int | None
    raw_name: str
    raw_category: str
    mapped_site_category: str
    count: int


class Command(BaseCommand):
    help = "Scoped remote Auto_DB sync for GPL TD articles into local clone (no Product writes)."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=20000, help="Max products to inspect")
        parser.add_argument("--from-csv", type=str, default="", help="Optional scoped input CSV (brand+td_article pairs)")
        parser.add_argument("--dry-run", action="store_true", help="Plan only, no local clone writes")
        parser.add_argument("--apply", action="store_true", help="Write only to local Auto_DB clone tables")
        parser.add_argument("--batch-size", type=int, default=100, help="Batch size for remote row operations")
        parser.add_argument("--remote-query-budget", type=int, default=0, help="Max remote queries per run (0 = unlimited)")
        parser.add_argument("--stop-on-remote-quota", action="store_true", help="Stop gracefully on remote quota")
        parser.add_argument(
            "--only-missing-local",
            action="store_true",
            help="Scope to pairs missing in local clone (current default behavior, compatibility flag).",
        )
        parser.add_argument("--resume", action="store_true", help="Resume from saved state key")
        parser.add_argument("--state-key", type=str, default="", help="State key for resumable runs")
        parser.add_argument("--export-csv", type=str, required=True, help="CSV path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier")
        limit = max(int(options.get("limit") or 0), 0)
        from_csv = str(options.get("from_csv") or "").strip()
        dry_run = bool(options.get("dry_run"))
        do_apply = bool(options.get("apply"))
        if dry_run == do_apply:
            raise CommandError("Specify exactly one mode: --dry-run or --apply.")
        batch_size = max(int(options.get("batch_size") or 100), 1)
        remote_query_budget = max(int(options.get("remote_query_budget") or 0), 0)
        stop_on_remote_quota = bool(options.get("stop_on_remote_quota"))
        only_missing_local = bool(options.get("only_missing_local"))
        resume = bool(options.get("resume"))
        state_key = str(options.get("state_key") or "").strip() or "gpl_td_articles_sync_default"
        export_csv = str(options.get("export_csv") or "").strip()
        if not export_csv:
            raise CommandError("Provide --export-csv")
        if resume and not state_key:
            raise CommandError("--resume requires --state-key")

        storage = AutoDbRawCloneStorage()
        scope_rows: dict[tuple[str, str], dict[str, str]] | None = None
        if from_csv:
            scope_rows = self._load_scope_from_csv(from_csv)
            if not scope_rows:
                raise CommandError(f"Scoped input CSV has no valid rows: {from_csv}")
        pairs = self._build_pair_scope(storage=storage, supplier_code=supplier_code, limit=limit, scope_rows=scope_rows)
        total_pairs = len(pairs)
        if total_pairs == 0:
            self._export_csv(path=export_csv, rows=[])
            self.stdout.write("autodb_sync_gpl_td_articles_from_remote summary:")
            self.stdout.write("- total_pairs: 0")
            self.stdout.write("- writes=0")
            self.stdout.write("- UTR calls=0")
            return

        source_table = f"gpl_td_articles_sync:{state_key}"
        start_index = 0
        state = AutoDbSyncState.objects.using("auto_db_pro").filter(source_table=source_table).first()
        if resume and state is not None:
            metadata = state.metadata if isinstance(state.metadata, dict) else {}
            previous_mode = str(metadata.get("mode") or "").strip().lower()
            # Do not reuse dry-run offset for apply mode: dry-run is planning only.
            if do_apply and (
                previous_mode == "dry_run"
                or (
                    previous_mode == ""
                    and str(state.status or "").strip().lower() == AutoDbSyncState.Status.COMPLETED
                    and int(state.processed_rows or 0) >= int(state.total_rows or 0)
                )
            ):
                start_index = 0
            else:
                start_index = max(int(state.last_offset or 0), 0)
        if start_index >= total_pairs:
            start_index = total_pairs if resume else 0

        counters = Counter()
        counters["total_pairs"] = total_pairs
        counters["selected_pairs"] = max(total_pairs - start_index, 0)
        rows_out: list[dict[str, str]] = []
        pending_prd_ids: set[int] = set()
        query_count = 0
        quota_exceeded = False
        aborted_budget = False
        last_offset = start_index
        local_pair_keys = {(item.supplier_id, normalize_article(item.lookup_article) or item.lookup_article) for item in pairs if item.supplier_id and item.lookup_article}
        local_existing = self._load_local_article_pairs(storage=storage, pairs=[(sid, art) for sid, art in local_pair_keys if sid and art])

        self._save_state(
            source_table=source_table,
            status=AutoDbSyncState.Status.RUNNING,
            total_rows=total_pairs,
            processed_rows=start_index,
            failed_rows=0,
            last_offset=start_index,
            metadata={
                "mode": "dry_run" if dry_run else "apply",
                "remote_query_budget": remote_query_budget,
                "stop_on_remote_quota": stop_on_remote_quota,
                "only_missing_local": only_missing_local,
            },
            started=True,
        )

        for chunk_start in range(start_index, total_pairs, batch_size):
            chunk = pairs[chunk_start : chunk_start + batch_size]
            last_offset = chunk_start + len(chunk)

            actionable: list[PairCandidate] = []
            for pair in chunk:
                if pair.supplier_id is None:
                    counters["brand_unresolved_pairs"] += 1
                    rows_out.append(self._row_from_pair(pair=pair, status="brand_unresolved", reason="supplier_not_resolved_local"))
                    continue
                if not pair.lookup_article:
                    counters["invalid_empty_td_article"] += 1
                    rows_out.append(self._row_from_pair(pair=pair, status="invalid_empty_article", reason="empty_lookup_article"))
                    continue
                article_key = normalize_article(pair.lookup_article) or pair.lookup_article
                marker = (int(pair.supplier_id), article_key)
                if marker in local_existing:
                    counters["local_already_present_pairs"] += 1
                    rows_out.append(self._row_from_pair(pair=pair, status="local_exists", reason="local_article_present"))
                    continue
                counters["missing_local_pairs"] += 1
                actionable.append(pair)

            if not actionable:
                counters["processed_pairs"] += len(chunk)
                continue

            if remote_query_budget > 0 and query_count >= remote_query_budget:
                aborted_budget = True
                break

            keys = [(int(item.supplier_id), str(item.lookup_article)) for item in actionable if item.supplier_id]
            articles_rows: list[dict[str, Any]] = []
            article_numbers_rows: list[dict[str, Any]] = []
            article_prd_rows: list[dict[str, Any]] = []
            by_key_articles: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
            by_key_numbers: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)

            try:
                query_count += 1
                articles_rows = storage.fetch_remote_rows_by_composite_keys(
                    table="articles",
                    first_column="supplierid",
                    second_column="datasupplierarticlenumber",
                    keys=keys,
                    limit=max(len(keys) * 4, batch_size),
                )
            except AutoDbProRemoteClientError as exc:
                message = str(exc)
                if stop_on_remote_quota and is_remote_quota_error(message):
                    quota_exceeded = True
                    break
                counters["remote_errors"] += 1
                for pair in actionable:
                    rows_out.append(self._row_from_pair(pair=pair, status="remote_error", reason=message[:240]))
                counters["processed_pairs"] += len(chunk)
                continue

            for row in articles_rows:
                marker = self._row_marker(row=row)
                if marker is not None:
                    by_key_articles[marker].append(row)

            unresolved_keys: list[tuple[int, str]] = []
            for pair in actionable:
                marker = (int(pair.supplier_id), normalize_article(pair.lookup_article) or pair.lookup_article)
                if marker not in by_key_articles:
                    unresolved_keys.append((int(pair.supplier_id), pair.lookup_article))

            if unresolved_keys:
                if remote_query_budget > 0 and query_count >= remote_query_budget:
                    aborted_budget = True
                    break
                try:
                    query_count += 1
                    article_numbers_rows = storage.fetch_remote_rows_by_composite_keys(
                        table="article_numbers",
                        first_column="supplierid",
                        second_column="datasupplierarticlenumber",
                        keys=unresolved_keys,
                        limit=max(len(unresolved_keys) * 4, batch_size),
                    )
                except AutoDbProRemoteClientError as exc:
                    message = str(exc)
                    if stop_on_remote_quota and is_remote_quota_error(message):
                        quota_exceeded = True
                        break
                    counters["remote_errors"] += 1
                    for pair in actionable:
                        rows_out.append(self._row_from_pair(pair=pair, status="remote_error", reason=message[:240]))
                    counters["processed_pairs"] += len(chunk)
                    continue

                for row in article_numbers_rows:
                    marker = self._row_marker(row=row)
                    if marker is not None:
                        by_key_numbers[marker].append(row)

            if do_apply:
                if articles_rows:
                    failed = storage.upsert_rows(table="articles", rows=articles_rows, sync_batch_id=state_key)
                    counters["articles_created_or_updated"] += max(len(articles_rows) - failed, 0)
                if article_numbers_rows:
                    failed = storage.upsert_rows(table="article_numbers", rows=article_numbers_rows, sync_batch_id=state_key)
                    counters["article_numbers_created_or_updated"] += max(len(article_numbers_rows) - failed, 0)
            else:
                counters["would_create_or_update_articles"] += len(articles_rows)
                counters["would_create_or_update_article_numbers"] += len(article_numbers_rows)

            hit_keys: list[tuple[int, str]] = []
            for pair in actionable:
                marker = (int(pair.supplier_id), normalize_article(pair.lookup_article) or pair.lookup_article)
                a_rows = by_key_articles.get(marker, [])
                n_rows = by_key_numbers.get(marker, [])
                remote_found = bool(a_rows or n_rows)
                if remote_found:
                    counters["remote_hits"] += 1
                    hit_keys.append((int(pair.supplier_id), pair.lookup_article))
                    rows_out.append(
                        self._row_from_pair(
                            pair=pair,
                            status="remote_found",
                            reason="remote_exact_supplierid_datasupplierarticlenumber_hit",
                            supplier_id=pair.supplier_id,
                            remote_found=True,
                            remote_title=self._pick_title(a_rows, n_rows),
                            remote_article_number=self._pick_article_number(a_rows, n_rows),
                        )
                    )
                else:
                    counters["remote_not_found"] += 1
                    rows_out.append(self._row_from_pair(pair=pair, status="remote_not_found", reason="remote_article_not_found"))

            if hit_keys and (remote_query_budget <= 0 or query_count < remote_query_budget):
                try:
                    query_count += 1
                    article_prd_rows = storage.fetch_remote_rows_by_composite_keys(
                        table="article_prd",
                        first_column="supplierid",
                        second_column="datasupplierarticlenumber",
                        keys=hit_keys,
                        limit=max(len(hit_keys) * 8, 200),
                    )
                except AutoDbProRemoteClientError as exc:
                    message = str(exc)
                    if stop_on_remote_quota and is_remote_quota_error(message):
                        quota_exceeded = True
                    else:
                        counters["remote_errors"] += 1
                    article_prd_rows = []

                if article_prd_rows:
                    counters["would_fetch_related_minimal"] += len(article_prd_rows)
                    if do_apply:
                        failed = storage.upsert_rows(table="article_prd", rows=article_prd_rows, sync_batch_id=state_key)
                        counters["article_prd_created_or_updated"] += max(len(article_prd_rows) - failed, 0)
                    for row in article_prd_rows:
                        for key in ("productid", "productId", "product_id"):
                            try:
                                value = int(row.get(key))
                            except (TypeError, ValueError):
                                continue
                            pending_prd_ids.add(value)
                            break

            counters["processed_pairs"] += len(chunk)
            self._save_state(
                source_table=source_table,
                status=AutoDbSyncState.Status.RUNNING,
                total_rows=total_pairs,
                processed_rows=min(last_offset, total_pairs),
                failed_rows=counters.get("remote_errors", 0),
                last_offset=min(last_offset, total_pairs),
                metadata={"remote_queries": query_count},
            )

            if quota_exceeded:
                break
            if remote_query_budget > 0 and query_count >= remote_query_budget:
                aborted_budget = True
                break

        # batched prd fetch (minimal related)
        if pending_prd_ids and (not quota_exceeded):
            sorted_ids = sorted(pending_prd_ids)
            for offset in range(0, len(sorted_ids), max(batch_size, 100)):
                if remote_query_budget > 0 and query_count >= remote_query_budget:
                    aborted_budget = True
                    break
                chunk = sorted_ids[offset : offset + max(batch_size, 100)]
                try:
                    query_count += 1
                    prd_rows = storage.fetch_remote_rows_in(
                        table="prd",
                        column="id",
                        values=chunk,
                        limit=max(len(chunk) * 2, 200),
                    )
                except AutoDbProRemoteClientError as exc:
                    message = str(exc)
                    if stop_on_remote_quota and is_remote_quota_error(message):
                        quota_exceeded = True
                        break
                    counters["remote_errors"] += 1
                    continue
                if prd_rows:
                    counters["would_fetch_related_minimal"] += len(prd_rows)
                    if do_apply:
                        failed = storage.upsert_rows(table="prd", rows=prd_rows, sync_batch_id=state_key)
                        counters["prd_created_or_updated"] += max(len(prd_rows) - failed, 0)

        status = AutoDbSyncState.Status.COMPLETED
        last_error = ""
        if quota_exceeded:
            status = AutoDbSyncState.Status.PAUSED
            counters["remote_quota_exceeded"] = 1
            last_error = "remote_quota_exceeded"
        elif aborted_budget:
            status = AutoDbSyncState.Status.PAUSED
            last_error = "remote_query_budget_reached"

        self._save_state(
            source_table=source_table,
            status=status,
            total_rows=total_pairs,
            processed_rows=last_offset,
            failed_rows=counters.get("remote_errors", 0),
            last_offset=last_offset,
            metadata={
                "remote_queries": query_count,
                "state_key": state_key,
                "mode": "dry_run" if dry_run else "apply",
                "remote_query_budget": remote_query_budget,
                "stop_on_remote_quota": stop_on_remote_quota,
                "only_missing_local": only_missing_local,
            },
            finished=status == AutoDbSyncState.Status.COMPLETED,
            last_error=last_error,
        )

        self._export_csv(path=export_csv, rows=rows_out)
        self.stdout.write("autodb_sync_gpl_td_articles_from_remote summary:")
        self.stdout.write(f"- mode: {'dry_run' if dry_run else 'apply'}")
        self.stdout.write(f"- scoped_from_csv: {from_csv or '-'}")
        self.stdout.write(f"- only_missing_local: {1 if only_missing_local else 0} (default_behavior=1)")
        self.stdout.write(f"- total_pairs: {counters.get('total_pairs', 0)}")
        self.stdout.write(f"- selected_pairs: {counters.get('selected_pairs', 0)}")
        self.stdout.write(f"- processed_pairs: {counters.get('processed_pairs', 0)}")
        self.stdout.write(f"- missing_local_pairs: {counters.get('missing_local_pairs', 0)}")
        self.stdout.write(f"- brand_unresolved_pairs: {counters.get('brand_unresolved_pairs', 0)}")
        self.stdout.write(f"- local_already_present_pairs: {counters.get('local_already_present_pairs', 0)}")
        self.stdout.write(f"- remote_queries: {query_count}")
        self.stdout.write(f"- remote_hits: {counters.get('remote_hits', 0)}")
        self.stdout.write(f"- remote_not_found: {counters.get('remote_not_found', 0)}")
        self.stdout.write(f"- remote_errors: {counters.get('remote_errors', 0)}")
        self.stdout.write(f"- remote_quota_exceeded: {counters.get('remote_quota_exceeded', 0)}")
        self.stdout.write(f"- would_create_articles: {counters.get('would_create_or_update_articles', 0)}")
        self.stdout.write(f"- would_update_articles: 0")
        self.stdout.write(f"- would_fetch_related_minimal: {counters.get('would_fetch_related_minimal', 0)}")
        self.stdout.write(f"- articles_created_or_updated: {counters.get('articles_created_or_updated', 0)}")
        self.stdout.write(f"- article_numbers_created_or_updated: {counters.get('article_numbers_created_or_updated', 0)}")
        self.stdout.write(f"- article_prd_created_or_updated: {counters.get('article_prd_created_or_updated', 0)}")
        self.stdout.write(f"- prd_created_or_updated: {counters.get('prd_created_or_updated', 0)}")
        self.stdout.write(f"- state_saved: 1")
        self.stdout.write(f"- state_key: {state_key}")
        self.stdout.write(f"- csv: {export_csv}")
        self.stdout.write("- Product writes=0")
        self.stdout.write("- SupplierOffer writes=0")
        self.stdout.write("- price/stock changed=0")
        self.stdout.write("- UTR calls=0")

    def _build_pair_scope(
        self,
        *,
        storage: AutoDbRawCloneStorage,
        supplier_code: str,
        limit: int,
        scope_rows: dict[tuple[str, str], dict[str, str]] | None = None,
    ) -> list[PairCandidate]:
        products_qs = (
            Product.objects.select_related("category", "brand")
            .filter(supplier_offers__supplier__code=supplier_code)
            .distinct()
            .order_by("id")
        )
        if limit > 0:
            products_qs = products_qs[:limit]
        products = list(products_qs)
        product_ids = [str(item.id) for item in products]
        latest_raw_map = self._latest_raw_offers_map(supplier_code=supplier_code, product_ids=product_ids)
        supplier_index = self._build_local_supplier_index(storage=storage)
        alias_index = self._build_alias_index()

        groups: dict[tuple[str, str], PairCandidate] = {}
        for product in products:
            pid = str(product.id)
            raw = latest_raw_map.get(pid)
            if raw is None:
                continue
            payload = raw.raw_payload if isinstance(raw.raw_payload, dict) else {}
            raw_brand = self._payload_pick(payload, ("Група ТД", "Группа ТД", "group")) or str(raw.brand_name or "").strip()
            td_article = self._payload_pick(payload, ("Артикул ТД", "Артикул ТД.", "article_td"))
            gpl_article = self._payload_pick(payload, ("Артикул", "article")) or str(raw.article or "").strip()
            lookup_article = td_article or gpl_article
            scope_key = (normalize_brand(raw_brand), normalize_article(td_article or lookup_article))
            if scope_rows is not None and scope_key not in scope_rows:
                continue

            scope_row = scope_rows.get(scope_key) if scope_rows is not None else None
            supplier_id = self._resolve_supplier_id_local(brand_name=raw_brand, supplier_index=supplier_index, alias_index=alias_index)
            if scope_row is not None:
                scoped_supplier_id = str(scope_row.get("supplier_id") or "").strip()
                try:
                    supplier_id = int(scoped_supplier_id)
                except (TypeError, ValueError):
                    pass
            key = (raw_brand, lookup_article)
            existing = groups.get(key)
            if existing is None:
                groups[key] = PairCandidate(
                    raw_brand=raw_brand,
                    td_article=td_article,
                    gpl_article=gpl_article,
                    lookup_article=lookup_article,
                    supplier_id=supplier_id,
                    raw_name=str(raw.product_name or "").strip(),
                    raw_category=self._payload_pick(payload, ("Категорія", "Категория", "category")),
                    mapped_site_category=str(getattr(product.category, "name", "") or ""),
                    count=1,
                )
            else:
                existing.count += 1
        out = list(groups.values())
        out.sort(key=lambda item: (normalize_brand(item.raw_brand), normalize_article(item.lookup_article), item.raw_brand, item.lookup_article))
        return out

    @staticmethod
    def _load_scope_from_csv(path: str) -> dict[tuple[str, str], dict[str, str]]:
        input_path = Path(path).expanduser()
        if not input_path.exists():
            raise CommandError(f"--from-csv not found: {input_path}")
        rows = list(csv.DictReader(input_path.open(encoding="utf-8")))
        out: dict[tuple[str, str], dict[str, str]] = {}
        for row in rows:
            raw_brand = str(row.get("raw_brand") or "").strip()
            td_article = str(row.get("raw_td_article") or row.get("td_article") or row.get("lookup_article") or "").strip()
            if not raw_brand or not td_article:
                continue
            marker = (normalize_brand(raw_brand), normalize_article(td_article))
            if marker not in out:
                out[marker] = {k: str(v or "").strip() for k, v in row.items()}
        return out

    @staticmethod
    def _payload_pick(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            value = str(payload.get(key) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _latest_raw_offers_map(*, supplier_code: str, product_ids: list[str]) -> dict[str, SupplierRawOffer]:
        if not product_ids:
            return {}
        rows = (
            SupplierRawOffer.objects.filter(source__code=supplier_code, matched_product_id__in=product_ids)
            .order_by("matched_product_id", "-updated_at", "-id")
            .only("id", "matched_product_id", "brand_name", "article", "product_name", "raw_payload", "external_sku")
        )
        out: dict[str, SupplierRawOffer] = {}
        for item in rows.iterator(chunk_size=500):
            key = str(item.matched_product_id or "")
            if key and key not in out:
                out[key] = item
        return out

    @staticmethod
    def _build_alias_index() -> dict[str, int]:
        out: dict[str, int] = {}
        aliases = (
            AutoDbSupplierBrandAlias.objects.filter(is_active=True)
            .order_by("-manual_confirmed", "-confidence", "updated_at", "id")
            .values("normalized_raw_brand", "autodb_supplier_id")
        )
        for row in aliases.iterator(chunk_size=500):
            key = normalize_brand(str(row.get("normalized_raw_brand") or ""))
            supplier_id = int(row.get("autodb_supplier_id") or 0)
            if key and supplier_id > 0 and key not in out:
                out[key] = supplier_id
        return out

    @staticmethod
    def _build_local_supplier_index(storage: AutoDbRawCloneStorage) -> dict[str, int]:
        columns = storage.get_local_columns("suppliers")
        if not columns:
            return {}
        names = [name for name in ("id", "matchcode", "description", "fulldescription") if storage.column_exists(table="suppliers", column=name)]
        if not names:
            return {}
        rows = storage.fetch_local_rows(table="suppliers", limit=100000, columns=names)
        out: dict[str, int] = {}
        for row in rows:
            supplier_id = int(row.get("id") or 0)
            if supplier_id <= 0:
                continue
            for field in ("matchcode", "description", "fulldescription"):
                key = normalize_brand(str(row.get(field) or ""))
                if key and key not in out:
                    out[key] = supplier_id
        return out

    @staticmethod
    def _resolve_supplier_id_local(*, brand_name: str, supplier_index: dict[str, int], alias_index: dict[str, int]) -> int | None:
        key = normalize_brand(brand_name)
        if not key:
            return None
        if key in alias_index:
            return int(alias_index[key])
        if key in supplier_index:
            return int(supplier_index[key])
        return None

    def _load_local_article_pairs(self, *, storage: AutoDbRawCloneStorage, pairs: list[tuple[int, str]]) -> set[tuple[int, str]]:
        if not pairs:
            return set()
        by_supplier: dict[int, set[str]] = defaultdict(set)
        for supplier_id, article in pairs:
            value = str(article or "").strip()
            if not value:
                continue
            by_supplier[int(supplier_id)].add(value)
            normalized = normalize_article(value)
            if normalized:
                by_supplier[int(supplier_id)].add(normalized)

        found: set[tuple[int, str]] = set()
        for table in ("article_numbers", "articles"):
            supplier_col = storage.first_existing_column(table=table, candidates=["supplierid", "supplier_id"])
            article_col = storage.first_existing_column(
                table=table,
                candidates=["datasupplierarticlenumber", "DataSupplierArticleNumber", "article", "articlenumber", "number"],
            )
            if not supplier_col or not article_col:
                continue
            for supplier_id, values in by_supplier.items():
                ordered_values = sorted(values)
                for offset in range(0, len(ordered_values), 800):
                    chunk = ordered_values[offset : offset + 800]
                    rows = storage.fetch_local_rows_in(
                        table=table,
                        column=article_col,
                        values=chunk,
                        extra_filters={supplier_col: supplier_id},
                        limit=max(len(chunk) * 4, 200),
                        columns=[supplier_col, article_col],
                    )
                    for row in rows:
                        raw_value = str(row.get(article_col) or "").strip()
                        if not raw_value:
                            continue
                        found.add((int(supplier_id), normalize_article(raw_value) or raw_value))
        return found

    @staticmethod
    def _row_from_pair(
        *,
        pair: PairCandidate,
        status: str,
        reason: str,
        supplier_id: int | None = None,
        remote_found: bool = False,
        remote_title: str = "",
        remote_article_number: str = "",
    ) -> dict[str, str]:
        return {
            "raw_brand": pair.raw_brand,
            "td_article": pair.td_article,
            "supplier_id": str(supplier_id or pair.supplier_id or ""),
            "remote_found": "1" if remote_found else "0",
            "remote_article_title": remote_title,
            "remote_normalized_description": remote_title,
            "remote_supplier_id": str(supplier_id or pair.supplier_id or ""),
            "remote_article_number": remote_article_number,
            "status": status,
            "reason": reason,
            "product_count": str(pair.count),
        }

    @staticmethod
    def _pick_title(articles_rows: list[dict[str, Any]], article_numbers_rows: list[dict[str, Any]]) -> str:
        for row in [*(articles_rows or []), *(article_numbers_rows or [])]:
            for key in ("normalizeddescription", "description", "Description", "NormalizedDescription", "ArticleDescription"):
                value = str(row.get(key) or "").strip()
                if value:
                    return value
        return ""

    @staticmethod
    def _pick_article_number(articles_rows: list[dict[str, Any]], article_numbers_rows: list[dict[str, Any]]) -> str:
        for row in [*(articles_rows or []), *(article_numbers_rows or [])]:
            for key in ("datasupplierarticlenumber", "DataSupplierArticleNumber", "articlenumber", "article", "number"):
                value = str(row.get(key) or "").strip()
                if value:
                    return value
        return ""

    @staticmethod
    def _row_marker(*, row: dict[str, Any]) -> tuple[int, str] | None:
        supplier_raw = row.get("supplierid")
        article_raw = (
            row.get("datasupplierarticlenumber")
            or row.get("DataSupplierArticleNumber")
            or row.get("articlenumber")
            or row.get("article")
            or row.get("number")
        )
        try:
            supplier_id = int(supplier_raw)
        except (TypeError, ValueError):
            return None
        article = str(article_raw or "").strip()
        if not article:
            return None
        return supplier_id, normalize_article(article) or article

    @staticmethod
    def _save_state(
        *,
        source_table: str,
        status: str,
        total_rows: int,
        processed_rows: int,
        failed_rows: int,
        last_offset: int,
        metadata: dict[str, Any],
        started: bool = False,
        finished: bool = False,
        last_error: str = "",
    ) -> None:
        state, _ = AutoDbSyncState.objects.using("auto_db_pro").get_or_create(source_table=source_table)
        now = timezone.now()
        state.status = status
        state.total_rows = total_rows
        state.processed_rows = processed_rows
        state.failed_rows = failed_rows
        state.last_offset = last_offset
        state.last_cursor = str(last_offset)
        state.metadata = metadata
        state.last_error = last_error
        if started and state.started_at is None:
            state.started_at = now
        if finished:
            state.finished_at = now
        state.save(
            using="auto_db_pro",
            update_fields=[
                "status",
                "total_rows",
                "processed_rows",
                "failed_rows",
                "last_offset",
                "last_cursor",
                "metadata",
                "last_error",
                "started_at",
                "finished_at",
                "updated_at",
            ],
        )

    @staticmethod
    def _export_csv(*, path: str, rows: list[dict[str, str]]) -> None:
        output = Path(path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "raw_brand",
            "td_article",
            "supplier_id",
            "remote_found",
            "remote_article_title",
            "remote_normalized_description",
            "remote_supplier_id",
            "remote_article_number",
            "status",
            "reason",
            "product_count",
        ]
        with output.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
