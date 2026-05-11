from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Count, QuerySet
from django.utils import timezone

from apps.catalog.models import Product
from apps.catalog.services.svom_sku import build_deterministic_svom_sku, is_valid_svom_sku


@dataclass(slots=True)
class BackfillRow:
    product_id: str
    product_sku: str
    article: str
    supplier_count: int | None
    has_svom_sku: bool
    existing_svom_sku: str
    generated_svom_sku: str
    collision_retry_counter: int
    action: str


class Command(BaseCommand):
    help = "Generate stable SVOM SKU for products. Supports multi-offer/all scopes, dry-run and apply modes."

    SCOPE_MULTI_OFFER = "multi_offer"
    SCOPE_ALL = "all"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist generated SVOM SKU values.")
        parser.add_argument(
            "--scope",
            type=str,
            choices=(self.SCOPE_MULTI_OFFER, self.SCOPE_ALL),
            default=self.SCOPE_MULTI_OFFER,
            help="Target scope: multi_offer (default) or all products.",
        )
        parser.add_argument("--limit", type=int, default=0, help="Optional max rows to process.")
        parser.add_argument("--sample-size", type=int, default=30, help="Rows to include in markdown sample.")
        parser.add_argument("--export-csv", type=str, default="", help="CSV output path.")
        parser.add_argument("--export-md", type=str, default="", help="Markdown summary output path.")

    def handle(self, *args, **options):
        apply_mode = bool(options.get("apply"))
        scope = str(options.get("scope") or self.SCOPE_MULTI_OFFER).strip() or self.SCOPE_MULTI_OFFER
        limit = max(int(options.get("limit") or 0), 0)
        sample_size = max(int(options.get("sample_size") or 30), 1)
        export_csv = str(options.get("export_csv") or "").strip()
        export_md = str(options.get("export_md") or "").strip()

        if not export_csv:
            suffix = "apply" if apply_mode else "dry"
            export_csv = f"/tmp/svom_sku_{scope}_backfill_{suffix}.csv"
        if not export_md:
            suffix = "apply" if apply_mode else "dry"
            export_md = f"/tmp/svom_sku_{scope}_backfill_{suffix}.md"

        queryset = self._scope_queryset(scope=scope)
        if limit:
            queryset = queryset[:limit]

        rows: list[BackfillRow] = []
        processed = 0
        already_has_svom_sku = 0
        would_generate = 0
        collision_products = 0
        collision_retries = 0
        regex_valid_generated = 0
        regex_invalid_generated = 0
        applied = 0
        products_total = self._scope_queryset(scope=scope).count()
        reserved_sku_values = self._load_reserved_sku_values()
        pending_updates: list[tuple[str, str, object]] = []

        for product in queryset.iterator(chunk_size=1000):
            processed += 1
            existing = str(getattr(product, "svom_sku", "") or "").strip()
            supplier_count_value = getattr(product, "supplier_count", None)
            supplier_count = int(supplier_count_value) if supplier_count_value is not None else None
            if existing:
                already_has_svom_sku += 1
                row = BackfillRow(
                    product_id=str(product.id),
                    product_sku=str(product.sku or ""),
                    article=str(product.article or ""),
                    supplier_count=supplier_count,
                    has_svom_sku=True,
                    existing_svom_sku=existing,
                    generated_svom_sku=existing,
                    collision_retry_counter=0,
                    action="kept_existing",
                )
                rows.append(row)
                continue

            generated, counter = self._resolve_unique_sku_for_product(
                product_id=str(product.id),
                reserved_sku_values=reserved_sku_values,
            )
            would_generate += 1
            if is_valid_svom_sku(generated):
                regex_valid_generated += 1
            else:
                regex_invalid_generated += 1
            if counter > 0:
                collision_products += 1
                collision_retries += 1
                collision_retries += counter - 1

            action = "would_generate"
            if apply_mode:
                pending_updates.append((generated, timezone.now(), str(product.id)))
                if len(pending_updates) >= 1000:
                    self._flush_updates(pending_updates)
                    pending_updates.clear()
                applied += 1
                action = "applied"

            row = BackfillRow(
                product_id=str(product.id),
                product_sku=str(product.sku or ""),
                article=str(product.article or ""),
                supplier_count=supplier_count,
                has_svom_sku=False,
                existing_svom_sku="",
                generated_svom_sku=generated,
                collision_retry_counter=counter,
                action=action,
            )
            rows.append(row)

        if apply_mode and pending_updates:
            self._flush_updates(pending_updates)
            pending_updates.clear()

        self._write_csv(path=Path(export_csv), rows=rows)
        self._write_md(
            path=Path(export_md),
            scope=scope,
            apply_mode=apply_mode,
            products_total=products_total,
            processed=processed,
            already_has_svom_sku=already_has_svom_sku,
            would_generate=would_generate,
            applied=applied,
            collision_products=collision_products,
            collision_retries=collision_retries,
            regex_valid_generated=regex_valid_generated,
            regex_invalid_generated=regex_invalid_generated,
            sample_rows=rows[:sample_size],
            export_csv=export_csv,
        )

        self.stdout.write(self.style.SUCCESS("SVOM SKU backfill finished"))
        self.stdout.write(f"- scope: {scope}")
        self.stdout.write(f"- mode: {'apply' if apply_mode else 'dry-run'}")
        self.stdout.write(f"- products_total: {products_total}")
        self.stdout.write(f"- processed: {processed}")
        self.stdout.write(f"- already_has_svom_sku: {already_has_svom_sku}")
        self.stdout.write(f"- would_generate: {would_generate}")
        self.stdout.write(f"- applied: {applied}")
        self.stdout.write(f"- collision_products: {collision_products}")
        self.stdout.write(f"- collision_retries: {collision_retries}")
        self.stdout.write(f"- regex_valid_generated: {regex_valid_generated}")
        self.stdout.write(f"- regex_invalid_generated: {regex_invalid_generated}")
        self.stdout.write(f"- csv: {export_csv}")
        self.stdout.write(f"- md: {export_md}")

    @staticmethod
    def _multi_offer_queryset() -> QuerySet[Product]:
        return (
            Product.objects.annotate(
                supplier_count=Count("supplier_offers__supplier_id", distinct=True),
            )
            .filter(supplier_count__gt=1)
            .only("id", "sku", "article", "svom_sku")
            .order_by("id")
        )

    @classmethod
    def _scope_queryset(cls, *, scope: str) -> QuerySet[Product]:
        if scope == cls.SCOPE_ALL:
            return Product.objects.only("id", "sku", "article", "svom_sku").order_by("id")
        return cls._multi_offer_queryset()

    @staticmethod
    def _load_reserved_sku_values() -> set[str]:
        return {
            str(value).strip()
            for value in Product.objects.exclude(svom_sku__isnull=True)
            .exclude(svom_sku__exact="")
            .values_list("svom_sku", flat=True)
            if str(value).strip()
        }

    @staticmethod
    def _resolve_unique_sku_for_product(*, product_id: str, reserved_sku_values: set[str], max_attempts: int = 10_000) -> tuple[str, int]:
        for counter in range(max_attempts):
            candidate = build_deterministic_svom_sku(product_id=product_id, counter=counter)
            if candidate in reserved_sku_values:
                continue
            reserved_sku_values.add(candidate)
            return candidate, counter
        raise RuntimeError(f"Unable to allocate unique SVOM SKU for product={product_id}")

    @staticmethod
    def _flush_updates(rows: list[tuple[str, object, str]]) -> None:
        with connection.cursor() as cursor:
            cursor.executemany(
                'UPDATE "catalog_product" SET "svom_sku" = %s, "updated_at" = %s WHERE "id" = %s::uuid',
                rows,
            )

    @staticmethod
    def _write_csv(*, path: Path, rows: list[BackfillRow]) -> None:
        path = path.expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "product_id",
                    "product_sku",
                    "article",
                    "supplier_count",
                    "has_svom_sku",
                    "existing_svom_sku",
                    "generated_svom_sku",
                    "collision_retry_counter",
                    "action",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "product_id": row.product_id,
                        "product_sku": row.product_sku,
                        "article": row.article,
                        "supplier_count": "" if row.supplier_count is None else row.supplier_count,
                        "has_svom_sku": "1" if row.has_svom_sku else "0",
                        "existing_svom_sku": row.existing_svom_sku,
                        "generated_svom_sku": row.generated_svom_sku,
                        "collision_retry_counter": row.collision_retry_counter,
                        "action": row.action,
                    }
                )

    @staticmethod
    def _write_md(
        *,
        path: Path,
        scope: str,
        apply_mode: bool,
        products_total: int,
        processed: int,
        already_has_svom_sku: int,
        would_generate: int,
        applied: int,
        collision_products: int,
        collision_retries: int,
        regex_valid_generated: int,
        regex_invalid_generated: int,
        sample_rows: list[BackfillRow],
        export_csv: str,
    ) -> None:
        path = path.expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# SVOM SKU Backfill",
            "",
            f"- scope: {scope}",
            f"- mode: {'apply' if apply_mode else 'dry-run'}",
            f"- products_total: {products_total}",
            f"- processed: {processed}",
            f"- already_has_svom_sku: {already_has_svom_sku}",
            f"- would_generate: {would_generate}",
            f"- applied: {applied}",
            f"- collision_products: {collision_products}",
            f"- collision_retries: {collision_retries}",
            f"- regex_valid_generated: {regex_valid_generated}",
            f"- regex_invalid_generated: {regex_invalid_generated}",
            f"- csv: {export_csv}",
            "",
            "## Sample",
            "",
            "| product_id | sku | article | supplier_count | existing_svom_sku | generated_svom_sku | collision_retry_counter | action |",
            "|---|---|---|---:|---|---|---:|---|",
        ]

        for row in sample_rows:
            lines.append(
                "| {product_id} | {product_sku} | {article} | {supplier_count} | {existing_svom_sku} | {generated_svom_sku} | {collision_retry_counter} | {action} |".format(
                    product_id=row.product_id,
                    product_sku=row.product_sku or "-",
                    article=row.article or "-",
                    supplier_count=row.supplier_count,
                    existing_svom_sku=row.existing_svom_sku or "-",
                    generated_svom_sku=row.generated_svom_sku or "-",
                    collision_retry_counter=row.collision_retry_counter,
                    action=row.action,
                )
            )

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
