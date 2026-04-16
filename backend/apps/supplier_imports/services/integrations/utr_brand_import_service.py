from __future__ import annotations

from dataclasses import asdict, dataclass

from apps.catalog.models import Brand
from apps.catalog.services import (
    find_brand_by_normalized_name,
    generate_unique_brand_slug,
    normalized_brand_name,
    sanitize_brand_name,
)
from apps.supplier_imports.models import SupplierBrandAlias
from apps.supplier_imports.selectors import ensure_default_import_sources, get_import_source_by_code


@dataclass(frozen=True)
class UtrBrandImportSummary:
    total_received: int
    processed: int
    created: int
    updated: int
    skipped: int
    duplicate_in_payload: int
    errors: int

    def as_dict(self) -> dict:
        return asdict(self)


class UtrBrandImportService:
    def import_rows(self, *, rows: list[dict], source_code: str = "utr") -> UtrBrandImportSummary:
        total_received = len(rows)
        processed = 0
        created = 0
        updated = 0
        skipped = 0
        duplicate_in_payload = 0
        errors = 0

        ensure_default_import_sources()
        source = get_import_source_by_code(source_code)
        supplier = source.supplier

        existing_brands = list(Brand.objects.only("id", "name", "slug", "is_active"))
        brands_by_normalized_name: dict[str, Brand] = {}
        used_slugs = {brand.slug for brand in existing_brands if brand.slug}

        for brand in existing_brands:
            normalized = normalized_brand_name(brand.name)
            if normalized and normalized not in brands_by_normalized_name:
                brands_by_normalized_name[normalized] = brand

        existing_aliases = list(
            SupplierBrandAlias.objects.filter(source=source)
            .select_related("canonical_brand")
            .only(
                "id",
                "source_id",
                "supplier_id",
                "canonical_brand_id",
                "canonical_brand_name",
                "supplier_brand_alias",
                "normalized_alias",
                "is_active",
            )
        )
        aliases_by_normalized_name: dict[str, SupplierBrandAlias] = {}
        for alias in existing_aliases:
            normalized_alias = alias.normalized_alias
            if normalized_alias and normalized_alias not in aliases_by_normalized_name:
                aliases_by_normalized_name[normalized_alias] = alias

        seen_payload_normalized_names: set[str] = set()

        for item in rows:
            if not isinstance(item, dict):
                skipped += 1
                continue

            incoming_name = sanitize_brand_name(str(item.get("name", "")))
            normalized = normalized_brand_name(incoming_name)
            if not normalized:
                skipped += 1
                continue

            if normalized in seen_payload_normalized_names:
                duplicate_in_payload += 1
                skipped += 1
                continue
            seen_payload_normalized_names.add(normalized)
            processed += 1

            existing = brands_by_normalized_name.get(normalized)
            canonical_brand: Brand | None = None
            row_created = False
            row_updated = False
            if existing is not None:
                canonical_brand = existing
                if not existing.is_active:
                    existing.is_active = True
                    row_updated = True
                    existing.save(update_fields=("is_active", "updated_at"))
            else:
                try:
                    slug = generate_unique_brand_slug(
                        name=incoming_name,
                        reserved_slugs=used_slugs,
                    )
                    canonical_brand = Brand.objects.create(
                        name=incoming_name,
                        slug=slug,
                        is_active=True,
                    )
                    row_created = True
                    brands_by_normalized_name[normalized] = canonical_brand
                    created += 1
                except Exception:
                    fallback = find_brand_by_normalized_name(name=incoming_name)
                    if fallback is not None:
                        canonical_brand = fallback
                        brands_by_normalized_name[normalized] = fallback
                        if not fallback.is_active:
                            fallback.is_active = True
                            fallback.save(update_fields=("is_active", "updated_at"))
                            row_updated = True
                    else:
                        errors += 1
                        continue

            try:
                alias = aliases_by_normalized_name.get(normalized)
                if alias is None:
                    alias = SupplierBrandAlias.objects.create(
                        source=source,
                        supplier=supplier,
                        canonical_brand=canonical_brand,
                        canonical_brand_name=canonical_brand.name if canonical_brand else incoming_name,
                        supplier_brand_alias=incoming_name,
                        is_active=True,
                        priority=100,
                    )
                    aliases_by_normalized_name[normalized] = alias
                    if not row_created:
                        row_updated = True
                else:
                    alias_changed = False
                    if alias.source_id != source.id:
                        alias.source = source
                        alias_changed = True
                    if alias.supplier_id != supplier.id:
                        alias.supplier = supplier
                        alias_changed = True
                    if canonical_brand is not None and alias.canonical_brand_id != canonical_brand.id:
                        alias.canonical_brand = canonical_brand
                        alias_changed = True
                    desired_canonical_name = canonical_brand.name if canonical_brand is not None else incoming_name
                    if alias.canonical_brand_name != desired_canonical_name:
                        alias.canonical_brand_name = desired_canonical_name
                        alias_changed = True
                    if alias.supplier_brand_alias != incoming_name:
                        alias.supplier_brand_alias = incoming_name
                        alias_changed = True
                    if not alias.is_active:
                        alias.is_active = True
                        alias_changed = True
                    if alias_changed:
                        alias.save(
                            update_fields=(
                                "source",
                                "supplier",
                                "canonical_brand",
                                "canonical_brand_name",
                                "supplier_brand_alias",
                                "is_active",
                                "updated_at",
                            )
                        )
                        row_updated = True
            except Exception:
                errors += 1
                continue

            if row_created:
                continue
            if row_updated:
                updated += 1
            else:
                skipped += 1

        return UtrBrandImportSummary(
            total_received=total_received,
            processed=processed,
            created=created,
            updated=updated,
            skipped=skipped,
            duplicate_in_payload=duplicate_in_payload,
            errors=errors,
        )
