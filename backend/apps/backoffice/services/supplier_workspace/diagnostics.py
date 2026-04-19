from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def log_brands_import_failure(*, supplier_code: str, exc: Exception) -> None:
    logger.warning("UTR brand import failure for supplier=%s: %s", supplier_code, str(exc))
