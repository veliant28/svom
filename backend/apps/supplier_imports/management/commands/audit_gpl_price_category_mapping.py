from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Category
from apps.supplier_imports.parsers.utils import parse_table_rows, parse_xlsx_rows
from apps.supplier_imports.selectors import ensure_default_import_sources, get_import_source_by_code
from apps.supplier_imports.services.gpl_category_mapping_audit import (
    STATUS_ACTIVE,
    STATUS_CONFLICT,
    STATUS_IGNORE,
    STATUS_MISSING,
    STATUS_REVIEW,
    GplCategoryMappingAuditor,
    build_suggested_slug,
    join_examples,
    normalize_text,
    priority_for_count,
)
from apps.supplier_imports.services.import_runner.preparation import collect_files


class Command(BaseCommand):
    help = "Read-only audit of local GPL price category/group mapping to seeded assignable leaf categories."

    def add_arguments(self, parser):
        parser.add_argument("--source", default="gpl", choices=["gpl"], help="Supplier import source code.")
        parser.add_argument("--path", default="", help="Optional explicit local GPL price file path.")
        parser.add_argument("--export-csv", required=True, help="Full audit CSV path.")
        parser.add_argument("--draft-csv", default="/tmp/gpl_category_mapping_draft_full.csv", help="Draft mapping CSV path.")
        parser.add_argument("--missing-csv", default="/tmp/gpl_missing_leaf_category_suggestions.csv", help="Missing leaf suggestions CSV path.")
        parser.add_argument("--needs-review-csv", default="/tmp/gpl_category_mapping_needs_review_top.csv", help="Needs-review top CSV path.")
        parser.add_argument("--examples-limit", type=int, default=10, help="Examples per category/group in CSV.")

    def handle(self, *args, **options):
        ensure_default_import_sources()
        source_code = str(options["source"]).strip().lower()
        examples_limit = max(int(options.get("examples_limit") or 10), 1)
        file_path = self._resolve_file(source_code=source_code, path=str(options.get("path") or ""))
        rows = self._read_rows(file_path=file_path)
        if not rows:
            raise CommandError(f"No rows found in GPL price file: {file_path}")

        columns = list(rows[0][1].keys())
        auditor = GplCategoryMappingAuditor()
        grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for _, row in rows:
            raw_category = str(row.get("Категорія") or row.get("category") or "").strip()
            raw_group = str(row.get("Група ТД") or row.get("group") or "").strip()
            grouped[(raw_category, raw_group)].append(row)

        category_count = len({key[0] for key in grouped})
        group_count = len({key[1] for key in grouped})
        rows_out: list[dict[str, str]] = []
        draft_rows: list[dict[str, str]] = []
        missing_rows: list[dict[str, str]] = []
        needs_rows: list[dict[str, str]] = []

        status_group_counts: Counter[str] = Counter()
        status_product_counts: Counter[str] = Counter()
        site_root_counts: Counter[str] = Counter()

        categories_by_slug = {
            item.slug: item
            for item in Category.objects.filter(is_active=True).select_related("parent", "parent__parent").only("id", "name", "slug", "parent_id", "parent__id", "parent__name", "parent__parent_id", "parent__parent__name", "is_assignable")
        }

        for (raw_category, raw_group), group_rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0][0], item[0][1])):
            decision = auditor.decide_group(rows=group_rows)
            target = categories_by_slug.get(decision.target_slug)
            leaf_exists = target is not None
            target_is_assignable = bool(target is not None and target.is_assignable and target.parent_id)
            if decision.status == STATUS_ACTIVE and not target_is_assignable:
                status = STATUS_CONFLICT
                reason = "target_not_assignable_leaf"
            elif decision.status == STATUS_ACTIVE and not leaf_exists:
                status = STATUS_MISSING
                reason = "target_leaf_missing"
            else:
                status = decision.status
                reason = decision.reason

            product_count = len(group_rows)
            status_group_counts[status] += 1
            status_product_counts[status] += product_count
            if decision.root_name:
                site_root_counts[decision.root_name] += product_count

            brand_counts = Counter(str(row.get("Група ТД") or "").strip() for row in group_rows if str(row.get("Група ТД") or "").strip())
            example_articles = join_examples(
                (str(row.get("Артикул ТД") or row.get("Артикул") or "") for row in group_rows),
                limit=examples_limit,
            )
            example_names = join_examples((str(row.get("Найменування") or "") for row in group_rows), limit=examples_limit)
            example_descriptions = join_examples((str(row.get("Опис") or "") for row in group_rows), limit=min(examples_limit, 5))
            top_brands = " | ".join(f"{brand}:{count}" for brand, count in brand_counts.most_common(10))

            row_out = {
                "raw_category": raw_category,
                "raw_group": raw_group,
                "product_count": str(product_count),
                "brand_count": str(len(brand_counts)),
                "top_brands": top_brands,
                "example_articles": example_articles,
                "example_names": example_names,
                "example_descriptions": example_descriptions,
                "proposed_root": decision.root_name,
                "proposed_leaf_category": decision.target_name,
                "proposed_leaf_slug": decision.target_slug,
                "leaf_exists": "yes" if leaf_exists else "no",
                "target_is_assignable": "yes" if target_is_assignable else "no",
                "confidence": f"{decision.confidence:.3f}",
                "reason": reason,
                "status": status,
            }
            rows_out.append(row_out)

            draft_rows.append(
                {
                    "supplier_code": source_code,
                    "raw_category": raw_category,
                    "raw_group": raw_group,
                    "target_leaf_slug": decision.target_slug if status == STATUS_ACTIVE else "",
                    "target_leaf_name": decision.target_name if status == STATUS_ACTIVE else "",
                    "target_root_name": decision.root_name,
                    "status": "active" if status == STATUS_ACTIVE else status,
                    "confidence": f"{decision.confidence:.3f}",
                    "reason": reason,
                    "product_count": str(product_count),
                    "top_brands": top_brands,
                    "examples": example_names,
                }
            )

            if status == STATUS_MISSING:
                suggested_name = decision.desired_leaf_name or raw_category or raw_group
                missing_rows.append(
                    {
                        "raw_category": raw_category,
                        "raw_group": raw_group,
                        "product_count": str(product_count),
                        "examples": example_names,
                        "suggested_root": decision.root_name,
                        "suggested_leaf_name": suggested_name,
                        "suggested_slug": build_suggested_slug(suggested_name),
                        "reason": reason,
                        "priority": priority_for_count(product_count),
                    }
                )

            if status in {STATUS_REVIEW, STATUS_CONFLICT, STATUS_MISSING}:
                needs_rows.append(
                    {
                        "raw_category": raw_category,
                        "raw_group": raw_group,
                        "product_count": str(product_count),
                        "top_brands": top_brands,
                        "examples": example_names,
                        "proposed_action": self._proposed_action(status=status, reason=reason),
                    }
                )

        needs_rows = sorted(needs_rows, key=lambda row: (-int(row["product_count"]), row["raw_category"], row["raw_group"]))[:100]

        self._export(path=str(options["export_csv"]), rows=rows_out)
        self._export(path=str(options["draft_csv"]), rows=draft_rows)
        self._export(path=str(options["missing_csv"]), rows=missing_rows)
        self._export(path=str(options["needs_review_csv"]), rows=needs_rows)

        stat = file_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        total_rows = len(rows)

        self.stdout.write("GPL price category mapping audit:")
        self.stdout.write(f"- file_path: {file_path}")
        self.stdout.write(f"- modified_time: {mtime}")
        self.stdout.write(f"- total_gpl_rows: {total_rows}")
        self.stdout.write(f"- detected_columns_count: {len(columns)}")
        self.stdout.write(f"- detected_columns: {columns}")
        self.stdout.write("- first_5_rows:")
        for _, row in rows[:5]:
            self.stdout.write(
                "  - "
                f"category={row.get('Категорія','')} group={row.get('Група ТД','')} "
                f"article={row.get('Артикул ТД') or row.get('Артикул','')} name={row.get('Найменування','')}"
            )
        self.stdout.write(f"- unique_category_count: {category_count}")
        self.stdout.write(f"- unique_group_count: {group_count}")
        self.stdout.write(f"- unique_category_group_pairs: {len(grouped)}")
        self.stdout.write(f"- export_csv: {options['export_csv']}")
        self.stdout.write(f"- draft_csv: {options['draft_csv']}")
        self.stdout.write(f"- missing_leaf_csv: {options['missing_csv']}")
        self.stdout.write(f"- needs_review_csv: {options['needs_review_csv']}")
        self.stdout.write("- coverage_summary:")
        for status in (STATUS_ACTIVE, STATUS_REVIEW, STATUS_MISSING, STATUS_CONFLICT, STATUS_IGNORE):
            product_count = status_product_counts.get(status, 0)
            pct = (product_count / total_rows * 100) if total_rows else 0.0
            self.stdout.write(
                f"  - {status}: groups={status_group_counts.get(status, 0)} products={product_count} coverage={pct:.2f}%"
            )
        self.stdout.write("- counts_by_proposed_site_root:")
        for root, count in site_root_counts.most_common():
            self.stdout.write(f"  - {root}: {count}")
        self.stdout.write("- top_30_unmapped_review_groups:")
        for row in [item for item in rows_out if item["status"] in {STATUS_REVIEW, STATUS_MISSING, STATUS_CONFLICT}][:30]:
            self.stdout.write(
                f"  - {row['product_count']} | {row['status']} | {row['raw_category']} | {row['raw_group']} | {row['reason']}"
            )
        self.stdout.write("- top_30_mapped_groups:")
        for row in [item for item in rows_out if item["status"] == STATUS_ACTIVE][:30]:
            self.stdout.write(
                f"  - {row['product_count']} | {row['proposed_root']} > {row['proposed_leaf_category']} | "
                f"{row['raw_category']} | {row['raw_group']} | conf={row['confidence']} | {row['reason']}"
            )
        self.stdout.write("- no GPL API calls")
        self.stdout.write("- no product import")
        self.stdout.write("- no offer import")
        self.stdout.write("- no Auto_DB link/enrichment")
        self.stdout.write("- no category creation from raw GPL")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _resolve_file(self, *, source_code: str, path: str) -> Path:
        if path.strip():
            candidate = Path(path).expanduser()
            if not candidate.exists():
                raise CommandError(f"GPL price file not found: {candidate}")
            return candidate.resolve()

        source = get_import_source_by_code(source_code)
        files = collect_files(source=source, file_paths=None)
        if not files:
            fallback = Path("/Users/vs/Django/svom/GPL.xlsx")
            if fallback.exists():
                return fallback.resolve()
            raise CommandError("No local GPL price file found.")
        return files[0]

    @staticmethod
    def _read_rows(*, file_path: Path) -> list[tuple[int, dict[str, str]]]:
        if file_path.suffix.lower() == ".xlsx":
            return parse_xlsx_rows(file_path)
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return parse_table_rows(content)

    @staticmethod
    def _export(*, path: str, rows: list[dict[str, str]]) -> None:
        out = Path(path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            out.write_text("", encoding="utf-8")
            return
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    @staticmethod
    def _proposed_action(*, status: str, reason: str) -> str:
        if status == STATUS_MISSING:
            return "add_leaf_to_taxonomy_or_map_to_existing_assignable_leaf"
        if status == STATUS_CONFLICT:
            return "split_raw_group_or_create_more_specific_mapping"
        if "no_confident" in normalize_text(reason):
            return "manual_review_raw_category_group"
        return "manual_review"
