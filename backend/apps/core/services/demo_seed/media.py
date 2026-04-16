from __future__ import annotations

import base64

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# 1x1 transparent PNG
_PLACEHOLDER_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA"
    "ASsJTYQAAAAASUVORK5CYII="
)
_PLACEHOLDER_PNG_BYTES = base64.b64decode(_PLACEHOLDER_PNG_BASE64)


def ensure_placeholder_media_file(path: str) -> str:
    if default_storage.exists(path):
        return path

    default_storage.save(path, ContentFile(_PLACEHOLDER_PNG_BYTES, name=path.rsplit("/", 1)[-1]))
    return path
