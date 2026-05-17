from __future__ import annotations

import json
from pathlib import Path
import re

from django.core.management.base import BaseCommand

from apps.catalog.models import Product
from apps.catalog.services.product_management import sanitize_product_name


class Command(BaseCommand):
    help = "Expand local product name glossary from manually locked Product translations."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write updated glossary file.")
        parser.add_argument("--limit", type=int, default=0, help="Limit scanned Product rows.")

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        limit = max(int(options.get("limit") or 0), 0)

        glossary_path = Path(__file__).resolve().parents[2] / "data" / "product_name_translations.json"
        existing_rows = self._read_glossary(path=glossary_path)

        existing_triples: set[tuple[str, str, str]] = set()
        existing_alias_keys: set[str] = set()
        for row in existing_rows:
            uk = sanitize_product_name(str(row.get("uk") or ""))
            ru = sanitize_product_name(str(row.get("ru") or ""))
            en = sanitize_product_name(str(row.get("en") or ""))
            if uk and ru and en:
                existing_triples.add((uk, ru, en))
            for key in self._iter_index_keys(row):
                existing_alias_keys.add(key)

        qs = (
            Product.objects.filter(name_manually_locked=True)
            .exclude(name_uk="")
            .exclude(name_ru="")
            .exclude(name_en="")
            .order_by("-updated_at")
        )
        if limit > 0:
            qs = qs[:limit]

        added: list[dict[str, object]] = []
        scanned = 0
        skipped_duplicate = 0
        skipped_invalid = 0

        for product in qs.iterator(chunk_size=500):
            scanned += 1
            uk = sanitize_product_name(str(product.name_uk or ""))
            ru = sanitize_product_name(str(product.name_ru or ""))
            en = sanitize_product_name(str(product.name_en or ""))
            if not self._is_valid_phrase(uk) or not self._is_valid_phrase(ru) or not self._is_valid_phrase(en):
                skipped_invalid += 1
                continue

            triple = (uk[:255], ru[:255], en[:255])
            if triple in existing_triples:
                skipped_duplicate += 1
                continue

            aliases: list[str] = []
            for candidate in (
                str(product.name_source_text or ""),
                str(product.name or ""),
                str(product.autodb_article_number or ""),
            ):
                clean = sanitize_product_name(candidate)[:255]
                if not self._is_valid_alias(clean):
                    continue
                if clean.lower() not in {item.lower() for item in aliases}:
                    aliases.append(clean)

            # Avoid huge noisy alias fanout: keep aliases that are not already indexed.
            filtered_aliases: list[str] = []
            for alias in aliases:
                key = self._normalize_key(alias)
                if not key or key in existing_alias_keys:
                    continue
                filtered_aliases.append(alias)
                existing_alias_keys.add(key)

            new_row = {
                "uk": triple[0],
                "ru": triple[1],
                "en": triple[2],
                "aliases": filtered_aliases,
            }
            added.append(new_row)
            existing_rows.append(new_row)
            existing_triples.add(triple)
            for key in self._iter_index_keys(new_row):
                existing_alias_keys.add(key)

        self.stdout.write("autodb_expand_product_name_glossary summary:")
        self.stdout.write(f"- scanned_manual_locked: {scanned}")
        self.stdout.write(f"- added_entries: {len(added)}")
        self.stdout.write(f"- skipped_duplicate: {skipped_duplicate}")
        self.stdout.write(f"- skipped_invalid: {skipped_invalid}")
        for sample in added[:10]:
            self.stdout.write(
                f"  - uk={sample.get('uk')} | ru={sample.get('ru')} | en={sample.get('en')} | aliases={len(sample.get('aliases') or [])}"
            )

        if apply_changes:
            serialized = json.dumps(existing_rows, ensure_ascii=False, indent=2)
            glossary_path.write_text(f"{serialized}\n", encoding="utf-8")
            self.stdout.write(f"- written: {glossary_path}")
        else:
            self.stdout.write("- dry_run_only: true (use --apply to write file)")

    def _read_glossary(self, *, path: Path) -> list[dict]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(payload, list):
            return []
        out: list[dict] = []
        for item in payload:
            if isinstance(item, dict):
                out.append(item)
        return out

    def _iter_index_keys(self, row: dict) -> list[str]:
        values = [
            str(row.get("uk") or ""),
            str(row.get("ru") or ""),
            str(row.get("en") or ""),
        ]
        aliases = row.get("aliases") or []
        if isinstance(aliases, list):
            values.extend(str(item or "") for item in aliases)
        return [key for key in (self._normalize_key(item) for item in values) if key]

    def _normalize_key(self, value: str) -> str:
        normalized = sanitize_product_name(value).lower()
        normalized = normalized.replace("ё", "е")
        return normalized

    def _is_valid_phrase(self, value: str) -> bool:
        if not value or len(value) < 3:
            return False
        return bool(re.search(r"[A-Za-zА-Яа-яІіЇїЄєҐґ]", value))

    def _is_valid_alias(self, value: str) -> bool:
        if not value or len(value) < 3:
            return False
        # Avoid filling glossary with pure article codes.
        if re.fullmatch(r"[A-Z0-9./+\-]{3,}", value.upper()):
            return False
        return self._is_valid_phrase(value)
