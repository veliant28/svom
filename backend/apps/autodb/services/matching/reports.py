from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def build_report_paths(*, command_name: str, run_id: str | None, export_prefix: str | None = None) -> tuple[Path, Path]:
    if export_prefix:
        prefix = Path(export_prefix).expanduser()
        return prefix.with_suffix(".csv"), prefix.with_suffix(".md")
    suffix = str(run_id or "no_run").replace("-", "")
    base = Path("/tmp") / f"{command_name}_{suffix}"
    return base.with_suffix(".csv"), base.with_suffix(".md")


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    materialized = [dict(row) for row in rows]
    fields: list[str] = []
    for row in materialized:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["result"])
        writer.writeheader()
        for row in materialized:
            writer.writerow({key: _stringify(row.get(key)) for key in fields})
    return len(materialized)


def write_md(path: Path, *, title: str, summary: Mapping[str, Any], csv_path: Path, rows_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "",
        f"- CSV: `{csv_path}`",
        f"- Rows: {rows_count}",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {_stringify(value)}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    *,
    command_name: str,
    run_id: str | None,
    rows: Iterable[Mapping[str, Any]],
    title: str,
    summary: Mapping[str, Any] | None = None,
    export_prefix: str | None = None,
) -> tuple[Path, Path, int]:
    csv_path, md_path = build_report_paths(command_name=command_name, run_id=run_id, export_prefix=export_prefix)
    rows_count = write_csv(csv_path, rows)
    write_md(md_path, title=title, summary=summary or {}, csv_path=csv_path, rows_count=rows_count)
    return csv_path, md_path, rows_count


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return repr(value)
    return str(value)
