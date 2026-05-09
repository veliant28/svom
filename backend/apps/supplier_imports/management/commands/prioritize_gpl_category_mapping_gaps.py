from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.supplier_imports.services.gpl_category_mapping_audit import build_suggested_slug, normalize_text


UNRESOLVED_STATUSES = {"missing_leaf_category", "needs_review", "conflict"}


class Command(BaseCommand):
    help = "Prioritize unresolved GPL category mapping gaps from read-only audit CSV."

    def add_arguments(self, parser):
        parser.add_argument("--audit-csv", required=True, help="Input audit CSV from audit_gpl_price_category_mapping.")
        parser.add_argument("--export-csv", required=True, help="Output prioritized unresolved gaps CSV.")

    def handle(self, *args, **options):
        audit_path = Path(str(options["audit_csv"])).expanduser()
        export_path = Path(str(options["export_csv"])).expanduser()
        if not audit_path.exists():
            raise CommandError(f"audit CSV not found: {audit_path}")

        rows = self._read_csv(audit_path)
        if not rows:
            raise CommandError(f"audit CSV is empty: {audit_path}")

        total_products = sum(self._int(row.get("product_count", "")) for row in rows)
        active_products = sum(
            self._int(row.get("product_count", "")) for row in rows if row.get("status") == "active_mapping_candidate"
        )
        unresolved = [row for row in rows if str(row.get("status") or "") in UNRESOLVED_STATUSES]
        unresolved.sort(key=lambda row: (-self._int(row.get("product_count", "")), row.get("status", ""), row.get("raw_category", ""), row.get("raw_group", "")))

        out_rows: list[dict[str, str]] = []
        for index, row in enumerate(unresolved, start=1):
            suggestion = self._suggest(row)
            out_rows.append(
                {
                    "priority_rank": str(index),
                    "status": str(row.get("status") or ""),
                    "raw_category": str(row.get("raw_category") or ""),
                    "raw_group": str(row.get("raw_group") or ""),
                    "product_count": str(row.get("product_count") or "0"),
                    "top_brands": str(row.get("top_brands") or ""),
                    "examples": str(row.get("example_names") or row.get("examples") or ""),
                    "current_proposed_root": str(row.get("proposed_root") or ""),
                    "current_proposed_leaf": str(row.get("proposed_leaf_category") or ""),
                    "current_reason": str(row.get("reason") or ""),
                    "suggested_action": suggestion["suggested_action"],
                    "suggested_root": suggestion["suggested_root"],
                    "suggested_leaf_name": suggestion["suggested_leaf_name"],
                    "suggested_leaf_slug": suggestion["suggested_leaf_slug"],
                    "confidence": suggestion["confidence"],
                    "reason": suggestion["reason"],
                }
            )

        self._write_csv(export_path, out_rows)

        self.stdout.write("GPL category mapping gaps priority report:")
        self.stdout.write(f"- audit_csv: {audit_path}")
        self.stdout.write(f"- export_csv: {export_path}")
        self.stdout.write(f"- total_products: {total_products}")
        self.stdout.write(f"- active_products_before: {active_products}")
        self.stdout.write(f"- unresolved_groups: {len(unresolved)}")
        self.stdout.write(f"- unresolved_products: {sum(self._int(row.get('product_count', '')) for row in unresolved)}")
        for limit in (10, 25, 50):
            resolved = sum(self._int(row.get("product_count", "")) for row in unresolved[:limit])
            projected = active_products + resolved
            coverage = (projected / total_products * 100) if total_products else 0.0
            self.stdout.write(f"- product_coverage_if_top_{limit}_resolved: {projected}/{total_products} ({coverage:.2f}%)")
        self.stdout.write("- top_30_unresolved_groups:")
        for item in out_rows[:30]:
            self.stdout.write(
                "  - "
                f"#{item['priority_rank']} {item['product_count']} | {item['status']} | "
                f"{item['raw_category']} | {item['raw_group']} | {item['suggested_action']} -> "
                f"{item['suggested_leaf_slug'] or item['suggested_leaf_name'] or '-'} | {item['reason']}"
            )
        self.stdout.write("- no GPL API calls")
        self.stdout.write("- no product import")
        self.stdout.write("- no offer import")
        self.stdout.write("- no Auto_DB link/enrichment")
        self.stdout.write("- no category creation from raw GPL")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        with path.open("r", newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "priority_rank",
            "status",
            "raw_category",
            "raw_group",
            "product_count",
            "top_brands",
            "examples",
            "current_proposed_root",
            "current_proposed_leaf",
            "current_reason",
            "suggested_action",
            "suggested_root",
            "suggested_leaf_name",
            "suggested_leaf_slug",
            "confidence",
            "reason",
        ]
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _suggest(self, row: dict[str, str]) -> dict[str, str]:
        status = str(row.get("status") or "")
        raw_category = str(row.get("raw_category") or "")
        raw_group = str(row.get("raw_group") or "")
        examples = str(row.get("example_names") or row.get("examples") or "")
        text = normalize_text(" ".join([raw_category, raw_group, examples]))

        if status == "conflict":
            return self._out("conflict_needs_manual_review", "", "", "", "0.500", "status_conflict_requires_manual_split")

        if "тяги та наконечники" in text:
            return self._out("split_mapping_needed", "Подвеска и рулевое", "Рулевые тяги / Рулевые наконечники", "", "0.880", "split_by_name_tiaga_vs_nakonechnik")
        if "пильовик" in text or "пыльник" in text:
            return self._out("split_mapping_needed", "Подвеска и рулевое / Сцепление и трансмиссия", "Пыльники и отбойники амортизаторов / Пыльник ШРУСа", "", "0.820", "split_by_name_shock_boot_vs_cv_boot")
        if "проклад" in text and "глуш" not in text:
            return self._out("split_mapping_needed", "Двигатель и выхлоп", "Прокладки по узлам", "", "0.720", "split_by_specific_gasket_name")

        exact_missing = (
            ("резонатор", "Двигатель и выхлоп", "Резонатор", "rezonator", "add_leaf_category", "resonator_leaf_needed"),
            ("труби приймальн", "Двигатель и выхлоп", "Приемная труба", "priemnaia-truba", "add_leaf_category", "front_exhaust_pipe_leaf_needed"),
            ("трубы приемн", "Двигатель и выхлоп", "Приемная труба", "priemnaia-truba", "add_leaf_category", "front_exhaust_pipe_leaf_needed"),
            ("труби випускн", "Двигатель и выхлоп", "Трубы выхлопной системы", "truby-vykhlopnoi-sistemy", "add_leaf_category", "exhaust_pipe_leaf_needed"),
            ("трубы выпускн", "Двигатель и выхлоп", "Трубы выхлопной системы", "truby-vykhlopnoi-sistemy", "add_leaf_category", "exhaust_pipe_leaf_needed"),
            ("ароматизатор", "Автохимия и аксессуары", "Ароматизаторы", "aromatizatory", "add_leaf_category", "air_freshener_leaf_needed"),
        )
        for token, root, leaf, slug, action, reason in exact_missing:
            if token in text:
                return self._out(action, root, leaf, slug, "0.920", reason)

        if status == "missing_leaf_category":
            leaf = raw_category or raw_group
            return self._out("add_leaf_category", str(row.get("proposed_root") or ""), leaf, build_suggested_slug(leaf), "0.550", "missing_leaf_from_audit")
        if status == "needs_review":
            return self._out("map_to_existing_leaf", str(row.get("proposed_root") or ""), str(row.get("proposed_leaf_category") or ""), str(row.get("proposed_leaf_slug") or ""), str(row.get("confidence") or "0.500"), "review_low_coverage_before_activation")
        return self._out("ignore", "", "", "", "0.000", "not_unresolved")

    @staticmethod
    def _out(action: str, root: str, leaf: str, slug: str, confidence: str, reason: str) -> dict[str, str]:
        return {
            "suggested_action": action,
            "suggested_root": root,
            "suggested_leaf_name": leaf,
            "suggested_leaf_slug": slug,
            "confidence": confidence,
            "reason": reason,
        }

    @staticmethod
    def _int(value: str) -> int:
        try:
            return int(str(value or "0"))
        except ValueError:
            return 0
