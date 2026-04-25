from __future__ import annotations

import json
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Category


DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "category_remaps"
DEFAULT_WAVE = "wave34_36_gbc_cleanup"


class Command(BaseCommand):
    help = (
        "Apply curated category cleanup waves. The command first ensures required "
        "categories exist with fixed UUIDs, then applies versioned remap rules. "
        "Dry-run is the default; use --apply to persist changes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--wave",
            default=DEFAULT_WAVE,
            help=f"Wave directory under supplier_imports/data/category_remaps. Default: {DEFAULT_WAVE}.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist category creation/updates and product remaps. Without this flag everything is rolled back.",
        )
        parser.add_argument(
            "--report-dir",
            default="/tmp/svom_curated_category_remaps",
            help="Directory where per-wave remap reports and a summary JSON are written.",
        )

    def handle(self, *args, **options):
        wave = str(options["wave"] or "").strip()
        if not wave:
            raise CommandError("--wave cannot be empty.")

        wave_dir = (DATA_ROOT / wave).resolve()
        if not wave_dir.exists() or not wave_dir.is_dir():
            raise CommandError(f"Unknown curated wave: {wave_dir}")
        try:
            wave_dir.relative_to(DATA_ROOT.resolve())
        except ValueError as exc:
            raise CommandError(f"Wave path escapes data root: {wave_dir}") from exc

        categories_json = wave_dir / "categories.json"
        if not categories_json.exists():
            raise CommandError(f"Missing categories.json: {categories_json}")

        rule_paths = sorted(wave_dir.glob("*_manual_rules.json"))
        if not rule_paths:
            raise CommandError(f"No *_manual_rules.json files found in curated wave: {wave_dir}")

        is_apply = bool(options["apply"])
        report_dir = Path(str(options["report_dir"])).expanduser().resolve()
        report_dir.mkdir(parents=True, exist_ok=True)

        categories = self._load_categories(categories_json)
        self._validate_category_parents(categories)
        self._validate_category_slugs(categories)

        mode = "apply" if is_apply else "dry-run"
        self.stdout.write(f"Running curated wave {wave} in {mode.upper()} mode")

        summary: dict = {
            "mode": mode,
            "wave": wave,
            "wave_dir": str(wave_dir),
            "generated_at": timezone.now().isoformat(),
            "categories": [],
            "reports": [],
        }

        with transaction.atomic():
            category_report = self._ensure_categories(categories)
            summary["categories"] = category_report

            for rule_path in rule_paths:
                report_path = report_dir / f"{wave}_{rule_path.stem}_{mode}.json"
                call_command(
                    "apply_product_category_remap_rules",
                    rules_json=str(rule_path),
                    lock_manual=True,
                    apply=is_apply,
                    report_json=str(report_path),
                    stdout=self.stdout,
                    stderr=self.stderr,
                )
                summary["reports"].append(str(report_path))

            if not is_apply:
                transaction.set_rollback(True)

        summary_path = report_dir / f"{wave}_summary_{mode}.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS("Curated category wave completed."))
        self.stdout.write(f"Summary: {summary_path}")
        if not is_apply:
            self.stdout.write("Dry-run mode: category changes and product remaps were rolled back.")

    @staticmethod
    def _load_categories(path: Path) -> list[dict]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        categories = payload.get("categories")
        if not isinstance(categories, list):
            raise CommandError(f"categories must be a list in {path}")

        result: list[dict] = []
        required_fields = {"id", "parent_id", "slug", "name", "name_uk", "name_ru", "name_en"}
        for index, raw_category in enumerate(categories, start=1):
            if not isinstance(raw_category, dict):
                raise CommandError(f"Category #{index} is not an object.")
            missing = sorted(field for field in required_fields if not str(raw_category.get(field) or "").strip())
            if missing:
                raise CommandError(f"Category #{index} has missing fields: {missing}")
            result.append(raw_category)
        return result

    @staticmethod
    def _validate_category_parents(categories: list[dict]) -> None:
        parent_ids = {str(category["parent_id"]) for category in categories}
        existing_parent_ids = {
            str(category_id)
            for category_id in Category.objects.filter(id__in=parent_ids).values_list("id", flat=True)
        }
        missing_parent_ids = sorted(parent_ids - existing_parent_ids)
        if missing_parent_ids:
            raise CommandError(f"Parent categories do not exist: {missing_parent_ids}")

    @staticmethod
    def _validate_category_slugs(categories: list[dict]) -> None:
        for category in categories:
            category_id = str(category["id"])
            slug = str(category["slug"])
            conflict = Category.objects.filter(slug=slug).exclude(id=category_id).first()
            if conflict:
                raise CommandError(
                    f"Slug {slug!r} is already used by category {conflict.id}; cannot create/update {category_id}."
                )

    @staticmethod
    def _ensure_categories(categories: list[dict]) -> list[dict]:
        report: list[dict] = []
        for category in categories:
            category_id = str(category["id"])
            defaults = {
                "parent_id": str(category["parent_id"]),
                "slug": str(category["slug"]),
                "name": str(category["name"]),
                "name_uk": str(category["name_uk"]),
                "name_ru": str(category["name_ru"]),
                "name_en": str(category["name_en"]),
                "description": str(category.get("description") or ""),
                "is_active": bool(category.get("is_active", True)),
            }
            obj, created = Category.objects.update_or_create(id=category_id, defaults=defaults)
            report.append(
                {
                    "id": str(obj.id),
                    "slug": obj.slug,
                    "created": created,
                    "parent_id": str(obj.parent_id) if obj.parent_id else None,
                }
            )
        return report
