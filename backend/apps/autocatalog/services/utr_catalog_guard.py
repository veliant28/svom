from __future__ import annotations

from django.conf import settings

UTR_CATALOG_DISABLED_WARNING = "UTR catalog enrichment is disabled"


def is_utr_catalog_enrichment_enabled() -> bool:
    return bool(getattr(settings, "UTR_CATALOG_ENRICHMENT_ENABLED", False))
