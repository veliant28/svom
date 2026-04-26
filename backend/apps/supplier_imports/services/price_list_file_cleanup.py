from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.supplier_imports.models import SupplierPriceList


@dataclass(frozen=True)
class PriceListFileCleanupResult:
    retention_hours: int
    cutoff_at: str
    files_deleted: int
    db_paths_cleared: int
    missing_files_cleared: int
    orphan_files_deleted: int
    unsafe_paths_skipped: int
    errors: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "retention_hours": self.retention_hours,
            "cutoff_at": self.cutoff_at,
            "files_deleted": self.files_deleted,
            "db_paths_cleared": self.db_paths_cleared,
            "missing_files_cleared": self.missing_files_cleared,
            "orphan_files_deleted": self.orphan_files_deleted,
            "unsafe_paths_skipped": self.unsafe_paths_skipped,
            "errors": self.errors,
        }


class SupplierPriceListFileCleanupService:
    def cleanup(self, *, retention_hours: int | None = None) -> PriceListFileCleanupResult:
        normalized_hours = max(
            int(retention_hours or getattr(settings, "SUPPLIER_PRICE_LIST_FILE_RETENTION_HOURS", 48)),
            1,
        )
        now = timezone.now()
        cutoff = now - timedelta(hours=normalized_hours)
        base_dir = Path(settings.MEDIA_ROOT) / "supplier_price_lists"
        base_resolved = base_dir.resolve(strict=False)

        files_deleted = 0
        db_paths_cleared = 0
        missing_files_cleared = 0
        orphan_files_deleted = 0
        unsafe_paths_skipped = 0
        errors = 0

        stale_rows = (
            SupplierPriceList.objects.filter(downloaded_file_path__gt="")
            .filter(Q(downloaded_at__lte=cutoff) | Q(downloaded_at__isnull=True, updated_at__lte=cutoff))
            .only("id", "status", "downloaded_file_path", "downloaded_at", "updated_at")
        )

        for row in stale_rows.iterator(chunk_size=500):
            file_path = Path(row.downloaded_file_path)
            resolved_path = file_path.resolve(strict=False)
            if not _is_relative_to(resolved_path, base_resolved):
                unsafe_paths_skipped += 1
                continue

            deleted_file = False
            if resolved_path.exists():
                if not resolved_path.is_file():
                    unsafe_paths_skipped += 1
                    continue
                try:
                    resolved_path.unlink()
                    files_deleted += 1
                    deleted_file = True
                except OSError:
                    errors += 1
                    continue
            else:
                missing_files_cleared += 1

            row.downloaded_file_path = ""
            update_fields = ["downloaded_file_path", "updated_at"]
            if row.status == SupplierPriceList.STATUS_DOWNLOADED:
                row.status = SupplierPriceList.STATUS_READY
                update_fields.append("status")
            row.save(update_fields=tuple(update_fields))
            db_paths_cleared += 1
            if not deleted_file:
                continue

        known_paths = _collect_known_downloaded_paths(base_resolved=base_resolved)
        if base_resolved.exists():
            for file_path in base_resolved.rglob("*"):
                try:
                    resolved_path = file_path.resolve(strict=False)
                    if not resolved_path.is_file():
                        continue
                    if resolved_path in known_paths:
                        continue
                    if _file_modified_after_cutoff(resolved_path, cutoff=cutoff):
                        continue
                    resolved_path.unlink()
                    files_deleted += 1
                    orphan_files_deleted += 1
                except OSError:
                    errors += 1

        return PriceListFileCleanupResult(
            retention_hours=normalized_hours,
            cutoff_at=cutoff.isoformat(),
            files_deleted=files_deleted,
            db_paths_cleared=db_paths_cleared,
            missing_files_cleared=missing_files_cleared,
            orphan_files_deleted=orphan_files_deleted,
            unsafe_paths_skipped=unsafe_paths_skipped,
            errors=errors,
        )


def _collect_known_downloaded_paths(*, base_resolved: Path) -> set[Path]:
    known_paths: set[Path] = set()
    for raw_path in SupplierPriceList.objects.filter(downloaded_file_path__gt="").values_list("downloaded_file_path", flat=True):
        resolved_path = Path(raw_path).resolve(strict=False)
        if _is_relative_to(resolved_path, base_resolved):
            known_paths.add(resolved_path)
    return known_paths


def _file_modified_after_cutoff(path: Path, *, cutoff) -> bool:
    modified_at = timezone.datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.get_current_timezone())
    return modified_at > cutoff


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True
