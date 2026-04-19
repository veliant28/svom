from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def error_reason_from_exception(exc: Exception) -> str:
    return type(exc).__name__


def log_publish_error(*, supplier_code: str, raw_offer_id: str, reason: str) -> None:
    logger.debug(
        "Mapped offer publish error supplier=%s raw_offer=%s reason=%s",
        supplier_code,
        raw_offer_id,
        reason,
    )
