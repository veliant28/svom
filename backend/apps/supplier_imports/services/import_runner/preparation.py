from __future__ import annotations

from pathlib import Path

from apps.supplier_imports.models import ImportSource


def collect_files(*, source: ImportSource, file_paths: list[str] | None) -> list[Path]:
    if file_paths:
        return sorted({Path(path).expanduser().resolve() for path in file_paths if path and Path(path).exists()})

    if not source.input_path:
        return []

    root = Path(source.input_path).expanduser()
    if not root.exists():
        return []

    if root.is_file():
        return [root.resolve()]

    patterns = source.file_patterns or ["*.json", "*.csv", "*.txt"]
    candidates: set[Path] = set()
    for pattern in patterns:
        for candidate in root.rglob(pattern):
            if candidate.is_file():
                candidates.add(candidate.resolve())

    return sorted(candidates)


def extract_utr_detail_id(*, source: ImportSource, raw_payload: dict) -> str:
    if source.code != "utr":
        return ""
    # UTR detail id must come from detail payload (details[].id), not from SKU/article/table rows.
    if not isinstance(raw_payload.get("brand"), dict):
        return ""

    detail_id = raw_payload.get("id")
    text = str(detail_id or "").strip()
    if not text.isdigit():
        return ""
    return text
