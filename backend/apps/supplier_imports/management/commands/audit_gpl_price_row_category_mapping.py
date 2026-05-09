from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Category
from apps.supplier_imports.parsers.utils import parse_table_rows, parse_xlsx_rows
from apps.supplier_imports.services.gpl_category_mapping_audit import (
    STATUS_ACTIVE,
    STATUS_CONFLICT,
    STATUS_MISSING,
    STATUS_REVIEW,
    GplCategoryMappingAuditor,
    build_suggested_slug,
)


UNRESOLVED_GROUP_STATUSES = {STATUS_REVIEW, STATUS_MISSING, STATUS_CONFLICT}


@dataclass(frozen=True)
class GroupSnapshot:
    status: str
    proposed_root: str
    proposed_leaf_name: str
    proposed_leaf_slug: str
    reason: str


class Command(BaseCommand):
    help = "Read-only row-level GPL category mapping audit (no writes, no import)."

    def add_arguments(self, parser):
        parser.add_argument("--source", default="gpl", choices=["gpl"], help="Supplier import source code.")
        parser.add_argument("--path", default="", help="Optional explicit local GPL price file path.")
        parser.add_argument("--export-csv", required=True, help="Row-level full audit CSV path.")
        parser.add_argument(
            "--unresolved-only-from",
            default="",
            help="Optional group-level audit CSV. When set, process only unresolved groups from this file.",
        )
        parser.add_argument(
            "--missing-leaf-csv",
            default="/tmp/gpl_row_mapping_missing_leaf_suggestions.csv",
            help="Missing leaf suggestions CSV path.",
        )
        parser.add_argument(
            "--draft-csv",
            default="/tmp/gpl_category_mapping_draft_row_level.csv",
            help="Draft row-level mapping CSV path.",
        )

    def handle(self, *args, **options):
        file_path = self._resolve_file(path=str(options.get("path") or ""))
        rows = self._read_rows(file_path=file_path)
        if not rows:
            raise CommandError(f"No rows found in GPL price file: {file_path}")

        unresolved_only_from = str(options.get("unresolved_only_from") or "").strip()
        group_snapshot = self._load_group_snapshot(path=unresolved_only_from) if unresolved_only_from else {}
        unresolved_only_keys = {
            key for key, item in group_snapshot.items() if item.status in UNRESOLVED_GROUP_STATUSES
        } if unresolved_only_from else set()

        auditor = GplCategoryMappingAuditor()
        all_categories_by_slug = {
            item.slug: item
            for item in Category.objects.filter(is_active=True).only("id", "name", "slug", "parent_id", "is_assignable")
        }

        if not group_snapshot:
            grouped_rows: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
            for _, row in rows:
                grouped_rows[self._group_key(row)].append(row)
            for key, grouped in grouped_rows.items():
                decision = auditor.decide_group(rows=grouped)
                group_snapshot[key] = GroupSnapshot(
                    status=decision.status,
                    proposed_root=decision.root_name,
                    proposed_leaf_name=decision.target_name,
                    proposed_leaf_slug=decision.target_slug,
                    reason=decision.reason,
                )

        out_rows: list[dict[str, str]] = []
        missing_leaf_suggestions: dict[tuple[str, str, str], dict[str, str | int]] = {}
        draft_counter: dict[tuple[str, str, str, str, str, str, str], dict[str, str | int]] = {}

        row_status_counts: Counter[str] = Counter()
        active_group_rows = 0
        active_row_rows = 0
        ignored_rows = 0

        for row_number, row in rows:
            group_key = self._group_key(row)
            if unresolved_only_keys and group_key not in unresolved_only_keys:
                continue

            group_item = group_snapshot.get(
                group_key,
                GroupSnapshot(status="unknown", proposed_root="", proposed_leaf_name="", proposed_leaf_slug="", reason=""),
            )
            group_status_before = group_item.status
            if group_status_before == STATUS_ACTIVE:
                active_group_rows += 1

            raw_category = str(row.get("Категорія") or row.get("category") or "").strip()
            raw_group = str(row.get("Група ТД") or row.get("group") or "").strip()
            name = str(row.get("Найменування") or row.get("name") or row.get("title") or "").strip()
            description = str(row.get("Опис") or row.get("description") or "").strip()
            brand = raw_group
            article = str(row.get("Артикул ТД") or row.get("Артикул") or row.get("article") or "").strip()

            target = auditor.classify_row(row=row)
            row_status = "needs_review"
            proposed_root = ""
            proposed_leaf_name = ""
            proposed_leaf_slug = ""
            target_exists = False
            target_is_assignable = False
            confidence = 0.0
            reason = ""
            matched_rule = ""

            if not raw_category and not raw_group and not name and not description:
                row_status = "ignored"
                reason = "empty_row"
                ignored_rows += 1
            elif target is not None:
                proposed_leaf_slug = str(target.slug or "").strip()
                confidence = float(target.confidence or 0.0)
                reason = str(target.reason or "").strip()
                matched_rule = reason
                category = all_categories_by_slug.get(proposed_leaf_slug)
                target_exists = category is not None
                target_is_assignable = bool(category is not None and category.is_assignable and category.parent_id)
                if target_is_assignable:
                    row_status = "active_row_mapping"
                    active_row_rows += 1
                    proposed_leaf_name = category.name
                    proposed_root = self._root_name(category)
                elif target_exists:
                    row_status = "conflict"
                    proposed_leaf_name = category.name
                    proposed_root = self._root_name(category)
                    reason = reason or "target_not_assignable_leaf"
                else:
                    row_status = "missing_leaf_category"
                    reason = reason or "target_slug_missing"
            else:
                if group_status_before == STATUS_MISSING:
                    row_status = "missing_leaf_category"
                    reason = "group_missing_leaf_no_row_signal"
                elif group_status_before == STATUS_CONFLICT:
                    row_status = "conflict"
                    reason = "group_conflict_no_row_signal"
                elif group_status_before == STATUS_REVIEW:
                    row_status = "needs_review"
                    reason = "no_confident_row_signal"
                else:
                    row_status = "needs_review"
                    reason = "no_confident_row_signal"

            row_status_counts[row_status] += 1

            out_rows.append(
                {
                    "row_number": str(row_number),
                    "raw_category": raw_category,
                    "raw_group": raw_group,
                    "brand": brand,
                    "article": article,
                    "name": name,
                    "description": description,
                    "group_status_before": group_status_before,
                    "row_mapping_status": row_status,
                    "proposed_root": proposed_root or group_item.proposed_root,
                    "proposed_leaf_name": proposed_leaf_name or group_item.proposed_leaf_name,
                    "proposed_leaf_slug": proposed_leaf_slug or group_item.proposed_leaf_slug,
                    "target_exists": "yes" if target_exists else "no",
                    "target_is_assignable": "yes" if target_is_assignable else "no",
                    "confidence": f"{confidence:.3f}",
                    "reason": reason,
                    "matched_rule": matched_rule,
                }
            )

            draft_key = (
                raw_category,
                raw_group,
                matched_rule or ("group_exact" if group_status_before == STATUS_ACTIVE else ""),
                proposed_leaf_slug or group_item.proposed_leaf_slug,
                proposed_leaf_name or group_item.proposed_leaf_name,
                row_status,
                f"{confidence:.3f}",
            )
            draft_item = draft_counter.setdefault(
                draft_key,
                {
                    "product_count": 0,
                    "examples": [],
                },
            )
            draft_item["product_count"] = int(draft_item["product_count"]) + 1
            if name and name not in draft_item["examples"]:
                draft_item["examples"].append(name)

            if row_status == "missing_leaf_category":
                suggested_leaf_name = (
                    proposed_leaf_name
                    or group_item.proposed_leaf_name
                    or raw_category
                    or raw_group
                    or "missing-category"
                )
                suggested_slug = (
                    proposed_leaf_slug
                    or group_item.proposed_leaf_slug
                    or build_suggested_slug(suggested_leaf_name)
                )
                suggested_root = proposed_root or group_item.proposed_root
                suggestion_key = (suggested_leaf_name, suggested_slug, suggested_root)
                suggestion = missing_leaf_suggestions.setdefault(
                    suggestion_key,
                    {
                        "suggested_leaf_name": suggested_leaf_name,
                        "suggested_slug": suggested_slug,
                        "suggested_root": suggested_root,
                        "product_count": 0,
                        "examples": [],
                        "reason": reason,
                    },
                )
                suggestion["product_count"] = int(suggestion["product_count"]) + 1
                if name and name not in suggestion["examples"]:
                    suggestion["examples"].append(name)

        draft_rows: list[dict[str, str]] = []
        for key, value in draft_counter.items():
            raw_category, raw_group, row_rule, target_leaf_slug, target_leaf_name, status, confidence = key
            draft_rows.append(
                {
                    "raw_category": raw_category,
                    "raw_group": raw_group,
                    "row_rule": row_rule,
                    "target_leaf_slug": target_leaf_slug,
                    "target_leaf_name": target_leaf_name,
                    "status": status,
                    "confidence": confidence,
                    "examples": " | ".join(value["examples"][:10]),
                    "product_count": str(value["product_count"]),
                }
            )
        draft_rows.sort(key=lambda item: (-int(item["product_count"]), item["raw_category"], item["raw_group"]))

        missing_rows: list[dict[str, str]] = []
        for value in missing_leaf_suggestions.values():
            count = int(value["product_count"])
            priority = "high" if count >= 100 else "medium" if count >= 25 else "low"
            missing_rows.append(
                {
                    "suggested_leaf_name": str(value["suggested_leaf_name"]),
                    "suggested_slug": str(value["suggested_slug"]),
                    "suggested_root": str(value["suggested_root"]),
                    "product_count": str(count),
                    "examples": " | ".join(list(value["examples"])[:10]),
                    "reason": str(value["reason"]),
                    "priority": priority,
                }
            )
        missing_rows.sort(key=lambda item: (-int(item["product_count"]), item["suggested_leaf_name"]))

        self._export(path=str(options["export_csv"]), rows=out_rows)
        self._export(path=str(options["missing_leaf_csv"]), rows=missing_rows)
        self._export(path=str(options["draft_csv"]), rows=draft_rows)

        total_rows = len(out_rows)
        total_active_rows = active_group_rows + active_row_rows
        active_coverage = (total_active_rows / total_rows * 100) if total_rows else 0.0

        unresolved_counter: Counter[tuple[str, str, str]] = Counter()
        for item in out_rows:
            status = item["row_mapping_status"]
            if status in {"needs_review", "missing_leaf_category", "conflict"}:
                unresolved_counter[(item["raw_category"], item["raw_group"], status)] += 1

        self.stdout.write("GPL row-level category mapping audit:")
        self.stdout.write(f"- file_path: {file_path}")
        self.stdout.write(f"- total_rows: {total_rows}")
        self.stdout.write(f"- unresolved_only_from: {unresolved_only_from or '-'}")
        self.stdout.write(f"- export_csv: {options['export_csv']}")
        self.stdout.write(f"- draft_csv: {options['draft_csv']}")
        self.stdout.write(f"- missing_leaf_csv: {options['missing_leaf_csv']}")
        self.stdout.write("- coverage_summary:")
        self.stdout.write(f"  - active_group_mapping_rows: {active_group_rows}")
        self.stdout.write(f"  - active_row_mapping_rows: {active_row_rows}")
        self.stdout.write(f"  - total_active_rows: {total_active_rows}")
        self.stdout.write(f"  - active_coverage: {active_coverage:.2f}%")
        self.stdout.write(f"  - needs_review_rows: {row_status_counts.get('needs_review', 0)}")
        self.stdout.write(f"  - missing_leaf_rows: {row_status_counts.get('missing_leaf_category', 0)}")
        self.stdout.write(f"  - conflict_rows: {row_status_counts.get('conflict', 0)}")
        self.stdout.write(f"  - ignored_rows: {row_status_counts.get('ignored', 0)}")

        self.stdout.write("- top_50_unresolved_grouped_rows:")
        for (raw_category, raw_group, status), count in unresolved_counter.most_common(50):
            self.stdout.write(f"  - {count} | {status} | {raw_category} | {raw_group}")

        self.stdout.write("- top_50_missing_leaf_suggestions:")
        for row in missing_rows[:50]:
            self.stdout.write(
                f"  - {row['product_count']} | {row['priority']} | {row['suggested_root']} | "
                f"{row['suggested_leaf_name']} | {row['suggested_slug']}"
            )

        self.stdout.write("- no GPL API calls")
        self.stdout.write("- no product import")
        self.stdout.write("- no offer import")
        self.stdout.write("- no Auto_DB link/enrichment")
        self.stdout.write("- no category creation from raw GPL")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    @staticmethod
    def _group_key(row: dict[str, str]) -> tuple[str, str]:
        raw_category = str(row.get("Категорія") or row.get("category") or "").strip()
        raw_group = str(row.get("Група ТД") or row.get("group") or "").strip()
        return raw_category, raw_group

    @staticmethod
    def _resolve_file(*, path: str) -> Path:
        if path.strip():
            candidate = Path(path).expanduser()
            if not candidate.exists():
                raise CommandError(f"GPL price file not found: {candidate}")
            return candidate.resolve()
        fallback = Path("/Users/vs/Django/svom/GPL.xlsx")
        if fallback.exists():
            return fallback.resolve()
        raise CommandError("No local GPL price file found. Pass --path explicitly.")

    @staticmethod
    def _read_rows(*, file_path: Path) -> list[tuple[int, dict[str, str]]]:
        if file_path.suffix.lower() == ".xlsx":
            return parse_xlsx_rows(file_path)
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return parse_table_rows(content)

    @staticmethod
    def _load_group_snapshot(*, path: str) -> dict[tuple[str, str], GroupSnapshot]:
        csv_path = Path(path).expanduser()
        if not csv_path.exists():
            raise CommandError(f"unresolved-only-from CSV not found: {csv_path}")
        out: dict[tuple[str, str], GroupSnapshot] = {}
        with csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                key = (
                    str(row.get("raw_category") or "").strip(),
                    str(row.get("raw_group") or "").strip(),
                )
                if not key[0] and not key[1]:
                    continue
                out[key] = GroupSnapshot(
                    status=str(row.get("status") or "").strip(),
                    proposed_root=str(row.get("proposed_root") or "").strip(),
                    proposed_leaf_name=str(row.get("proposed_leaf_category") or "").strip(),
                    proposed_leaf_slug=str(row.get("proposed_leaf_slug") or "").strip(),
                    reason=str(row.get("reason") or "").strip(),
                )
        return out

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
    def _root_name(category: Category) -> str:
        current = category
        while current.parent_id:
            current = current.parent  # type: ignore[assignment]
            if current is None:
                return ""
        return current.name
