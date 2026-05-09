from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.supplier_imports.parsers.utils import parse_table_rows, parse_xlsx_rows
from apps.supplier_imports.selectors import get_import_source_by_code
from apps.supplier_imports.services.gpl_category_mapping_audit import normalize_text
from apps.supplier_imports.services.gpl_import_category_assignment import (
    MAPPING_STATUS_ASSIGNED_GROUP,
    MAPPING_STATUS_ASSIGNED_ROW,
    MAPPING_STATUS_CONFLICT,
    MAPPING_STATUS_IGNORED,
    MAPPING_STATUS_MISSING,
    MAPPING_STATUS_NEEDS,
    GplImportCategoryAssignmentResolver,
    GroupAssignmentDecision,
)
from apps.supplier_imports.services.import_runner.preparation import collect_files


UNRESOLVED_STATUSES = {
    MAPPING_STATUS_NEEDS,
    MAPPING_STATUS_MISSING,
    MAPPING_STATUS_CONFLICT,
}


class Command(BaseCommand):
    help = "Read-only preflight simulation of GPL import category assignment (no writes)."

    def add_arguments(self, parser):
        parser.add_argument("--source", default="gpl", choices=["gpl"], help="Supplier import source code.")
        parser.add_argument("--path", default="", help="Optional explicit local GPL price file path.")
        parser.add_argument("--export-csv", required=True, help="Full row-level preflight CSV path.")
        parser.add_argument("--unresolved-csv", required=True, help="Unresolved row-level preflight CSV path.")
        parser.add_argument("--summary-csv", required=True, help="Preflight summary CSV path.")
        parser.add_argument(
            "--unresolved-groups-csv",
            default="/tmp/gpl_import_category_preflight_unresolved_groups.csv",
            help="Grouped unresolved summary CSV path (top 100 by product_count).",
        )

    def handle(self, *args, **options):
        source_code = str(options.get("source") or "gpl").strip().lower()
        file_path = self._resolve_file(source_code=source_code, path=str(options.get("path") or ""))
        rows = self._read_rows(file_path=file_path)
        if not rows:
            raise CommandError(f"No rows found in GPL price file: {file_path}")

        grouped_rows: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for _, row in rows:
            grouped_rows[self._group_key(row)].append(row)

        resolver = GplImportCategoryAssignmentResolver()
        group_decisions: dict[tuple[str, str], GroupAssignmentDecision] = {}
        for key, group in grouped_rows.items():
            group_decisions[key] = resolver.decide_group(rows=group)

        full_rows: list[dict[str, str]] = []
        unresolved_rows: list[dict[str, str]] = []
        unresolved_groups: dict[tuple[str, str, str], dict] = {}

        status_counts: Counter[str] = Counter()
        invalid_target_count = 0
        non_assignable_target_count = 0
        missing_target_count = 0

        for row_number, row in rows:
            raw_category = str(row.get("Категорія") or row.get("category") or "").strip()
            raw_group = str(row.get("Група ТД") or row.get("group") or "").strip()
            brand = str(row.get("brand") or raw_group).strip()
            article = str(row.get("Артикул ТД") or row.get("Артикул") or row.get("article") or "").strip()
            name = str(row.get("Найменування") or row.get("name") or row.get("title") or "").strip()
            description = str(row.get("Опис") or row.get("description") or "").strip()

            group_decision = group_decisions.get((raw_category, raw_group))
            row_decision = resolver.decide_row(row=row, group_decision=group_decision)

            invalid_target_count += int(row_decision.invalid_target)
            non_assignable_target_count += int(row_decision.non_assignable_target)
            missing_target_count += int(row_decision.missing_target)
            status_counts[row_decision.mapping_status] += 1

            full_row = {
                "row_number": str(row_number),
                "raw_category": raw_category,
                "raw_group": raw_group,
                "brand": brand,
                "article": article,
                "name": name,
                "description": description,
                "proposed_category_slug": row_decision.proposed_category_slug,
                "proposed_category_name": row_decision.proposed_category_name,
                "proposed_root_name": row_decision.proposed_root_name,
                "category_id": row_decision.category_id,
                "category_is_assignable": "true" if row_decision.category_is_assignable else "false",
                "mapping_status": row_decision.mapping_status,
                "matched_rule": row_decision.matched_rule,
                "confidence": f"{row_decision.confidence:.3f}",
                "reason": row_decision.reason,
            }
            full_rows.append(full_row)

            if row_decision.mapping_status in UNRESOLVED_STATUSES:
                unresolved_rows.append(full_row)
                group_key = (row_decision.mapping_status, raw_category, raw_group)
                bucket = unresolved_groups.setdefault(
                    group_key,
                    {
                        "status": row_decision.mapping_status,
                        "raw_category": raw_category,
                        "raw_group": raw_group,
                        "product_count": 0,
                        "brand_counter": Counter(),
                        "example_articles": [],
                        "example_names": [],
                        "reason_counter": Counter(),
                    },
                )
                bucket["product_count"] += 1
                if brand:
                    bucket["brand_counter"][brand] += 1
                if article and article not in bucket["example_articles"]:
                    bucket["example_articles"].append(article)
                if name and name not in bucket["example_names"]:
                    bucket["example_names"].append(name)
                if row_decision.reason:
                    bucket["reason_counter"][row_decision.reason] += 1

        total_rows = len(full_rows)
        assigned_group = status_counts.get(MAPPING_STATUS_ASSIGNED_GROUP, 0)
        assigned_row = status_counts.get(MAPPING_STATUS_ASSIGNED_ROW, 0)
        total_assigned = assigned_group + assigned_row
        assigned_pct = (total_assigned / total_rows * 100.0) if total_rows else 0.0

        summary_rows = [
            {
                "total_rows": str(total_rows),
                "assigned_by_group_mapping": str(assigned_group),
                "assigned_by_row_rule": str(assigned_row),
                "total_assigned": str(total_assigned),
                "total_assigned_pct": f"{assigned_pct:.2f}",
                "needs_category_mapping": str(status_counts.get(MAPPING_STATUS_NEEDS, 0)),
                "missing_leaf_category": str(status_counts.get(MAPPING_STATUS_MISSING, 0)),
                "conflict": str(status_counts.get(MAPPING_STATUS_CONFLICT, 0)),
                "ignored": str(status_counts.get(MAPPING_STATUS_IGNORED, 0)),
                "invalid_target_count": str(invalid_target_count),
                "non_assignable_target_count": str(non_assignable_target_count),
                "missing_target_count": str(missing_target_count),
            }
        ]

        unresolved_group_rows: list[dict[str, str]] = []
        for (status, raw_category, raw_group), payload in unresolved_groups.items():
            reason = payload["reason_counter"].most_common(1)[0][0] if payload["reason_counter"] else ""
            top_brands = " | ".join(f"{name}:{count}" for name, count in payload["brand_counter"].most_common(5))
            example_articles = " | ".join(payload["example_articles"][:5])
            example_names = " | ".join(payload["example_names"][:5])
            suggestion = self._suggest_unresolved_action(
                status=status,
                raw_category=raw_category,
                raw_group=raw_group,
                reason=reason,
                example_names=example_names,
            )
            unresolved_group_rows.append(
                {
                    "status": status,
                    "raw_category": raw_category,
                    "raw_group": raw_group,
                    "product_count": str(payload["product_count"]),
                    "top_brands": top_brands,
                    "example_articles": example_articles,
                    "example_names": example_names,
                    "reason": reason,
                    "suggested_action": suggestion["suggested_action"],
                    "suggested_target_leaf": suggestion["suggested_target_leaf"],
                    "suggested_root": suggestion["suggested_root"],
                }
            )

        unresolved_group_rows.sort(key=lambda item: (-int(item["product_count"]), item["status"], item["raw_category"], item["raw_group"]))
        unresolved_group_rows = unresolved_group_rows[:100]

        self._export_csv(path=str(options["export_csv"]), rows=full_rows)
        self._export_csv(path=str(options["unresolved_csv"]), rows=unresolved_rows)
        self._export_csv(path=str(options["summary_csv"]), rows=summary_rows)
        self._export_csv(path=str(options["unresolved_groups_csv"]), rows=unresolved_group_rows)

        self.stdout.write("GPL import category assignment preflight:")
        self.stdout.write(f"- file_path: {file_path}")
        self.stdout.write(f"- total_rows: {total_rows}")
        self.stdout.write(f"- export_csv: {options['export_csv']}")
        self.stdout.write(f"- unresolved_csv: {options['unresolved_csv']}")
        self.stdout.write(f"- summary_csv: {options['summary_csv']}")
        self.stdout.write(f"- unresolved_groups_csv: {options['unresolved_groups_csv']}")
        self.stdout.write("- mapping_summary:")
        self.stdout.write(f"  - assigned_by_group_mapping: {assigned_group}")
        self.stdout.write(f"  - assigned_by_row_rule: {assigned_row}")
        self.stdout.write(f"  - total_assigned: {total_assigned}")
        self.stdout.write(f"  - total_assigned_pct: {assigned_pct:.2f}%")
        self.stdout.write(f"  - needs_category_mapping: {status_counts.get(MAPPING_STATUS_NEEDS, 0)}")
        self.stdout.write(f"  - missing_leaf_category: {status_counts.get(MAPPING_STATUS_MISSING, 0)}")
        self.stdout.write(f"  - conflict: {status_counts.get(MAPPING_STATUS_CONFLICT, 0)}")
        self.stdout.write(f"  - ignored: {status_counts.get(MAPPING_STATUS_IGNORED, 0)}")
        self.stdout.write("- target_validation:")
        self.stdout.write(f"  - invalid_target_count: {invalid_target_count}")
        self.stdout.write(f"  - non_assignable_target_count: {non_assignable_target_count}")
        self.stdout.write(f"  - missing_target_count: {missing_target_count}")

        self.stdout.write("- top_50_unresolved_groups:")
        for item in unresolved_group_rows[:50]:
            self.stdout.write(
                f"  - {item['product_count']} | {item['status']} | {item['raw_category']} | {item['raw_group']} | {item['suggested_action']}"
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
    def _resolve_file(*, source_code: str, path: str) -> Path:
        if path.strip():
            candidate = Path(path).expanduser()
            if not candidate.exists():
                raise CommandError(f"GPL price file not found: {candidate}")
            return candidate.resolve()

        try:
            source = get_import_source_by_code(source_code)
            files = collect_files(source=source, file_paths=None)
            if files:
                return files[0].resolve()
        except Exception:  # noqa: BLE001
            pass

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
    def _export_csv(*, path: str, rows: list[dict[str, str]]) -> None:
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

    def _suggest_unresolved_action(
        self,
        *,
        status: str,
        raw_category: str,
        raw_group: str,
        reason: str,
        example_names: str,
    ) -> dict[str, str]:
        text = normalize_text(" ".join([raw_category, raw_group, reason, example_names]))

        suggested_root = self._suggest_root(text=text)
        suggested_target_leaf = ""

        split_heavy_tokens = (
            "датчик",
            "датчики",
            "проклад",
            "пильовик",
            "пыльник",
            "подшип",
            "підшип",
            "bearing",
            "трос",
            "кабель",
            "cable",
            "цилиндр",
            "циліндр",
        )
        low_conf_chem_tokens = (
            "краск",
            "эмал",
            "емал",
            "фарб",
            "абраз",
            "перчат",
            "рукавич",
            "хим",
            "очист",
            "аксесс",
            "аромат",
        )

        if status == MAPPING_STATUS_MISSING:
            suggested_action = "add_leaf"
            suggested_target_leaf = raw_category or raw_group
        elif status == MAPPING_STATUS_CONFLICT:
            if any(token in text for token in split_heavy_tokens):
                suggested_action = "add_row_rule"
            else:
                suggested_action = "needs_manual_decision"
        else:
            if any(token in text for token in split_heavy_tokens):
                suggested_action = "add_row_rule"
            elif any(token in text for token in low_conf_chem_tokens):
                suggested_action = "keep_review"
            elif "unknown" in text or "невідом" in text:
                suggested_action = "ignore"
            else:
                suggested_action = "needs_manual_decision"

        if "резонатор" in text:
            suggested_target_leaf = suggested_target_leaf or "Резонатор"
        elif "глуш" in text:
            suggested_target_leaf = suggested_target_leaf or "Глушитель"
        elif "пильов" in text or "пыльник" in text:
            suggested_target_leaf = suggested_target_leaf or "Пыльник ШРУСа / Пыльник рулевой тяги / Пыльники и отбойники амортизаторов"
        elif "датчик" in text:
            suggested_target_leaf = suggested_target_leaf or "Датчик ABS / Датчик температуры / Датчик давления"
        elif "проклад" in text:
            suggested_target_leaf = suggested_target_leaf or "Прокладка ГБЦ / Прокладка клапанной крышки / Прокладка глушителя / Прокладка поддона"
        elif "цилиндр" in text or "циліндр" in text:
            suggested_target_leaf = suggested_target_leaf or "Главный тормозной цилиндр / Рабочий тормозной цилиндр"

        return {
            "suggested_action": suggested_action,
            "suggested_target_leaf": suggested_target_leaf,
            "suggested_root": suggested_root,
        }

    @staticmethod
    def _suggest_root(*, text: str) -> str:
        if any(token in text for token in ("торм", "гальм", "brake", "цилиндр", "циліндр")):
            return "Тормозная система"
        if any(token in text for token in ("амортиз", "рулев", "рульов", "подвес", "підвіс", "ступиц", "сайлент", "bearing", "підшип", "подшип")):
            return "Подвеска и рулевое"
        if any(token in text for token in ("шрус", "сцеп", "зчеп", "кпп", "трансмис", "трос")):
            return "Сцепление и трансмиссия"
        if any(token in text for token in ("двиг", "мотор", "выхлоп", "випуск", "глуш", "резонатор", "проклад", "приймаль")):
            return "Двигатель и выхлоп"
        if any(token in text for token in ("датчик", "ламп", "фара", "генератор", "стартер", "акум", "аккум", "cable", "кабель")):
            return "Электрика и освещение"
        if any(token in text for token in ("краск", "эмал", "емал", "фарб", "антифриз", "adblue", "хим", "аксесс", "аромат", "абраз", "рукавич", "перчат")):
            return "Автохимия и аксессуары"
        return "needs_manual_decision"
