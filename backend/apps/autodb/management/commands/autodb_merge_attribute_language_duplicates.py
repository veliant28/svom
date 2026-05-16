from __future__ import annotations

from collections import defaultdict
import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from apps.catalog.models import Attribute, AttributeValue, ProductAttribute
from apps.catalog.services.product_management import sanitize_product_name


class Command(BaseCommand):
    help = "Merge duplicated AutoDB attributes created in different language variants (e.g. висота/высота)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes. By default runs in dry-run mode.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        attrs = list(
            Attribute.objects.filter(source=Attribute.SOURCE_AUTODB_PRO)
            .only("id", "name", "name_uk", "name_ru", "name_en", "source", "autodb_attribute_id")
            .order_by("id")
        )
        pa_counts = dict(
            ProductAttribute.objects.values("attribute_id")
            .annotate(count=Count("id"))
            .values_list("attribute_id", "count")
        )

        groups: dict[str, list[Attribute]] = defaultdict(list)
        for attr in attrs:
            key = self._normalize_key(str(attr.name or ""))
            if not key:
                continue
            groups[key].append(attr)

        merged_groups = 0
        deleted_attributes = 0
        moved_product_attributes = 0
        merged_product_attributes = 0
        moved_values = 0
        deleted_values = 0

        for key, bucket in groups.items():
            if len(bucket) <= 1:
                continue

            canonical = self._pick_canonical(bucket=bucket, pa_counts=pa_counts)
            duplicates = [attr for attr in bucket if attr.id != canonical.id]
            if not duplicates:
                continue

            merged_groups += 1
            best_ru = self._pick_best_ru_name(bucket=bucket, fallback=str(canonical.name or ""))

            if apply_changes:
                with transaction.atomic():
                    self._apply_canonical_names(canonical=canonical, best_ru=best_ru)
                    for duplicate in duplicates:
                        result = self._merge_attribute_into_canonical(canonical=canonical, duplicate=duplicate)
                        deleted_attributes += result["deleted_attributes"]
                        moved_product_attributes += result["moved_product_attributes"]
                        merged_product_attributes += result["merged_product_attributes"]
                        moved_values += result["moved_values"]
                        deleted_values += result["deleted_values"]
            else:
                for duplicate in duplicates:
                    deleted_attributes += 1
                    moved_product_attributes += ProductAttribute.objects.filter(attribute=duplicate).count()
                    moved_values += AttributeValue.objects.filter(attribute=duplicate).count()

            self.stdout.write(
                f"- key={key} canonical={canonical.id} canonical_name={best_ru} duplicates={len(duplicates)}"
            )

        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(f"AutoDB attribute language merge finished mode={mode}")
        self.stdout.write(f"- merged_groups: {merged_groups}")
        self.stdout.write(f"- deleted_attributes: {deleted_attributes}")
        self.stdout.write(f"- moved_product_attributes: {moved_product_attributes}")
        self.stdout.write(f"- merged_product_attributes: {merged_product_attributes}")
        self.stdout.write(f"- moved_values: {moved_values}")
        self.stdout.write(f"- deleted_values: {deleted_values}")

    def _normalize_key(self, value: str) -> str:
        normalized = sanitize_product_name(value).lower()
        normalized = normalized.replace("ё", "е").replace("ы", "и").replace("ъ", "").replace("ь", "")
        normalized = normalized.replace("і", "и").replace("ї", "и").replace("є", "е").replace("ґ", "г")
        normalized = re.sub(r"[^a-zа-я0-9]+", " ", normalized, flags=re.IGNORECASE)
        return sanitize_product_name(normalized)

    def _pick_canonical(self, *, bucket: list[Attribute], pa_counts: dict[str, int]) -> Attribute:
        def score(attr: Attribute) -> tuple[int, int, int]:
            name = str(attr.name or "")
            name_ru = str(attr.name_ru or "")
            score_value = 0
            if sanitize_product_name(name) and sanitize_product_name(name) == sanitize_product_name(name_ru):
                score_value += 5
            if re.search(r"[ыэёъ]", name.lower()):
                score_value += 3
            if re.search(r"[іїєґ]", name.lower()):
                score_value -= 2
            score_value += min(int(pa_counts.get(attr.id, 0)), 100) // 10
            # higher score first, then higher usage, then smaller id.
            return (score_value, int(pa_counts.get(attr.id, 0)), -int(str(attr.id.int)))

        return sorted(bucket, key=score, reverse=True)[0]

    def _pick_best_ru_name(self, *, bucket: list[Attribute], fallback: str) -> str:
        candidates: list[str] = []
        for attr in bucket:
            name = sanitize_product_name(str(attr.name or ""))
            name_ru = sanitize_product_name(str(attr.name_ru or ""))
            if name_ru:
                candidates.append(name_ru)
            if name:
                candidates.append(name)

        def rank(name: str) -> tuple[int, int]:
            score_value = 0
            if re.search(r"[ыэёъ]", name.lower()):
                score_value += 4
            if re.search(r"[іїєґ]", name.lower()):
                score_value -= 2
            return score_value, len(name)

        if not candidates:
            return sanitize_product_name(fallback)
        return sorted(candidates, key=rank, reverse=True)[0]

    def _apply_canonical_names(self, *, canonical: Attribute, best_ru: str) -> None:
        updates: list[str] = []
        clean_ru = sanitize_product_name(best_ru)
        if clean_ru and sanitize_product_name(str(canonical.name or "")) != clean_ru:
            canonical.name = clean_ru
            updates.append("name")
        if clean_ru and sanitize_product_name(str(canonical.name_ru or "")) != clean_ru:
            canonical.name_ru = clean_ru
            updates.append("name_ru")
        if updates:
            updates.append("updated_at")
            canonical.save(update_fields=tuple(dict.fromkeys(updates)))

    def _merge_attribute_into_canonical(self, *, canonical: Attribute, duplicate: Attribute) -> dict[str, int]:
        moved_values = 0
        deleted_values = 0
        moved_product_attributes = 0
        merged_product_attributes = 0

        for value_obj in AttributeValue.objects.filter(attribute=duplicate).order_by("id"):
            target = AttributeValue.objects.filter(attribute=canonical, value=value_obj.value).order_by("id").first()
            if target is None:
                target = AttributeValue.objects.filter(attribute=canonical, value__iexact=value_obj.value).order_by("id").first()
            if target is None:
                value_obj.attribute = canonical
                value_obj.save(update_fields=("attribute", "updated_at"))
                moved_values += 1
            else:
                ProductAttribute.objects.filter(attribute=duplicate, attribute_value=value_obj).update(attribute_value=target)
                value_obj.delete()
                deleted_values += 1

        for item in ProductAttribute.objects.filter(attribute=duplicate).order_by("id"):
            existing = ProductAttribute.objects.filter(product_id=item.product_id, attribute=canonical).order_by("id").first()
            if existing is None:
                item.attribute = canonical
                item.save(update_fields=("attribute", "updated_at"))
                moved_product_attributes += 1
                continue

            updates: list[str] = []
            if existing.attribute_value_id is None and item.attribute_value_id is not None and not existing.manual_locked:
                existing.attribute_value_id = item.attribute_value_id
                updates.append("attribute_value")
            if not existing.raw_value and item.raw_value:
                existing.raw_value = item.raw_value
                updates.append("raw_value")
            if updates:
                updates.append("updated_at")
                existing.save(update_fields=tuple(dict.fromkeys(updates)))
            item.delete()
            merged_product_attributes += 1

        duplicate.delete()
        return {
            "deleted_attributes": 1,
            "moved_product_attributes": moved_product_attributes,
            "merged_product_attributes": merged_product_attributes,
            "moved_values": moved_values,
            "deleted_values": deleted_values,
        }
