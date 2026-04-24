from __future__ import annotations

from pathlib import Path

from apps.supplier_imports.parsers.utils import parse_table_rows, parse_xlsx_rows

from .types import FileMetadata


def extract_file_metadata(*, source_file: Path | None, supplier_code: str) -> FileMetadata:
    if source_file is None or not source_file.exists() or not source_file.is_file():
        return FileMetadata.empty()

    headers: list[str] = []
    row_count = 0
    suffix = source_file.suffix.lower()

    if suffix == ".xlsx":
        rows = parse_xlsx_rows(source_file)
        row_count = len(rows)
        headers = list(rows[0][1].keys()) if rows else []
    else:
        content = source_file.read_text(encoding="utf-8", errors="ignore")
        rows = parse_table_rows(content)
        row_count = len(rows)
        headers = list(rows[0][1].keys()) if rows else []

    price_columns = detect_price_columns(headers=headers)
    warehouse_columns = detect_warehouse_columns(
        headers=headers,
        supplier_code=supplier_code,
        price_columns=price_columns,
    )
    file_size_bytes = source_file.stat().st_size

    return FileMetadata(
        file_name=source_file.name,
        file_path=str(source_file),
        file_size_bytes=file_size_bytes,
        file_size_label=human_size(file_size_bytes),
        warehouse_columns=warehouse_columns,
        price_columns=price_columns,
        row_count=row_count,
    )


def detect_price_columns(*, headers: list[str]) -> list[str]:
    columns: list[str] = []
    for header in headers:
        key = header.lower()
        if (
            "ціна" in key
            or "price" in key
            or "ррц" in key
            or key.startswith("price_")
        ):
            columns.append(header)
    return columns


def detect_warehouse_columns(*, headers: list[str], supplier_code: str, price_columns: list[str]) -> list[str]:
    if supplier_code == "utr":
        core = {
            "артикул utr",
            "артикул",
            "найменування",
            "бренд",
            "валюта",
            "ціна",
            "код",
            "категорія",
            "опис",
            "група тд",
            "артикул тд",
            "зображення товару",
        }
        return [
            header
            for header in headers
            if header.lower() not in core and header not in price_columns
        ]

    return [
        header
        for header in headers
        if "склад" in header.lower()
        or "warehouse" in header.lower()
        or header.lower().startswith("count_warehouse_")
    ]


def resolve_source_file_path(raw_path: str, *, preferred_extension: str | None = None) -> Path | None:
    if not raw_path.strip():
        return None
    path = Path(raw_path).expanduser()
    if not path.exists():
        return None
    preferred_suffix = ""
    if preferred_extension:
        normalized = preferred_extension.strip().lower()
        if normalized:
            preferred_suffix = normalized if normalized.startswith(".") else f".{normalized}"
    if path.is_file():
        if not preferred_suffix or path.suffix.lower() == preferred_suffix:
            return path.resolve()
        candidates = sorted(
            [
                item
                for item in path.parent.rglob(f"*{preferred_suffix}")
                if item.is_file()
            ],
            key=lambda item: item.stat().st_mtime,
        )
        return candidates[-1].resolve() if candidates else None
    if path.is_dir():
        if preferred_suffix:
            candidates = sorted(
                [
                    item
                    for item in path.rglob(f"*{preferred_suffix}")
                    if item.is_file()
                ],
                key=lambda item: item.stat().st_mtime,
            )
        else:
            candidates = sorted(
                [item for item in path.rglob("*") if item.is_file()],
                key=lambda item: item.stat().st_mtime,
            )
        return candidates[-1].resolve() if candidates else None
    return None


def resolve_extension(*, requested_format: str, source_file_name: str) -> str:
    format_key = requested_format.strip().lower()
    if format_key in {"xlsx", "csv", "txt", "json"}:
        return format_key
    if source_file_name and "." in source_file_name:
        return source_file_name.rsplit(".", 1)[-1].lower()
    return "xlsx"


def human_size(size: int) -> str:
    if size <= 0:
        return ""
    steps = ["B", "KB", "MB", "GB"]
    value = float(size)
    step = 0
    while value >= 1024 and step < len(steps) - 1:
        value /= 1024
        step += 1
    if step == 0:
        return f"{int(value)} {steps[step]}"
    return f"{value:.1f} {steps[step]}"
