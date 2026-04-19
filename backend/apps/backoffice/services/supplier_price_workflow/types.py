from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FileMetadata:
    file_name: str
    file_path: str
    file_size_bytes: int
    file_size_label: str
    warehouse_columns: list[str]
    price_columns: list[str]
    row_count: int

    @classmethod
    def empty(cls) -> "FileMetadata":
        return cls(
            file_name="",
            file_path="",
            file_size_bytes=0,
            file_size_label="",
            warehouse_columns=[],
            price_columns=[],
            row_count=0,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "file_size_label": self.file_size_label,
            "warehouse_columns": self.warehouse_columns,
            "price_columns": self.price_columns,
            "row_count": self.row_count,
        }
