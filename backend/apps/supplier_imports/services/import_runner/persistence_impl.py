from __future__ import annotations

from django.db import transaction

from apps.supplier_imports.models import ImportArtifact, ImportRun, ImportSource
from apps.supplier_imports.parsers import ParseResult
from apps.supplier_imports.services.gpl_import_category_assignment import GplImportCategoryAssignmentResolver

from .persistence_current_offers import persist_current_offer_rows
from .persistence_helpers import _uses_current_offer_persistence, attach_utr_detail_id, create_row_error, uses_current_offer_persistence
from .persistence_raw_history import persist_raw_history_rows


@transaction.atomic
def persist_parsed_rows(
    service,
    *,
    run: ImportRun,
    source: ImportSource,
    artifact: ImportArtifact,
    parse_result: ParseResult,
    dry_run: bool,
    matcher,
    supplier_offer_sync,
    article_normalizer,
    brand_resolver,
) -> tuple[int, int, int, int, set[str]]:
    if _uses_current_offer_persistence(source=source):
        return persist_current_offer_rows(
            service,
            run=run,
            source=source,
            artifact=artifact,
            parse_result=parse_result,
            dry_run=dry_run,
            matcher=matcher,
            article_normalizer=article_normalizer,
            brand_resolver=brand_resolver,
        )

    return persist_raw_history_rows(
        service,
        run=run,
        source=source,
        artifact=artifact,
        parse_result=parse_result,
        dry_run=dry_run,
        matcher=matcher,
        supplier_offer_sync=supplier_offer_sync,
        article_normalizer=article_normalizer,
        brand_resolver=brand_resolver,
    )


__all__ = [
    "GplImportCategoryAssignmentResolver",
    "attach_utr_detail_id",
    "create_row_error",
    "persist_current_offer_rows",
    "persist_parsed_rows",
    "persist_raw_history_rows",
    "uses_current_offer_persistence",
]
