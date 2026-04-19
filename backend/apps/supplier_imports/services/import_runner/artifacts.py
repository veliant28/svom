from __future__ import annotations

import hashlib
from pathlib import Path

from apps.supplier_imports.models import ImportArtifact, ImportRun, ImportSource


def create_artifact(*, run: ImportRun, source: ImportSource, file_path: Path) -> ImportArtifact:
    file_bytes = file_path.read_bytes()
    checksum = hashlib.sha1(file_bytes).hexdigest()  # noqa: S324

    return ImportArtifact.objects.create(
        run=run,
        source=source,
        file_name=file_path.name,
        file_path=str(file_path),
        file_format=file_path.suffix.lstrip(".").lower(),
        file_size=len(file_bytes),
        checksum_sha1=checksum,
        status=ImportArtifact.STATUS_PENDING,
    )
