from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError
from django.utils.translation import gettext as _

from .types import UtrImportCommandOptions


def normalize_options(raw_options: Mapping[str, Any]) -> UtrImportCommandOptions:
    limit = raw_options.get("limit")
    offset = max(0, int(raw_options.get("offset") or 0))
    resolve_until_empty = bool(raw_options.get("resolve_until_empty"))
    retry_unresolved = bool(raw_options.get("retry_unresolved"))
    resolve_only = bool(raw_options.get("resolve_only"))
    resolve_utr_articles = bool(
        raw_options.get("resolve_utr_articles") or resolve_until_empty or retry_unresolved or resolve_only
    )
    products_only = bool(raw_options.get("products_only"))
    missing_applicability_only = bool(raw_options.get("missing_applicability_only"))
    resolve_limit = raw_options.get("resolve_limit")
    resolve_offset = max(0, int(raw_options.get("resolve_offset") or 0))

    batch_size = raw_options.get("batch_size")
    if not batch_size or int(batch_size) <= 0:
        batch_size = int(getattr(settings, "UTR_BATCH_SIZE", 25))
    batch_size = max(int(batch_size), 1)

    options = UtrImportCommandOptions(
        limit=limit,
        offset=offset,
        resolve_utr_articles=resolve_utr_articles,
        resolve_limit=resolve_limit,
        resolve_offset=resolve_offset,
        resolve_until_empty=resolve_until_empty,
        retry_unresolved=retry_unresolved,
        resolve_only=resolve_only,
        products_only=products_only,
        missing_applicability_only=missing_applicability_only,
        batch_size=batch_size,
    )
    validate_options(options)
    return options


def validate_options(options: UtrImportCommandOptions) -> None:
    if options.products_only and (
        options.resolve_utr_articles
        or options.resolve_until_empty
        or options.retry_unresolved
        or options.resolve_only
    ):
        raise CommandError(_("--products-only нельзя комбинировать с resolve-опциями."))

    if options.resolve_until_empty and options.retry_unresolved:
        raise CommandError(_("--resolve-until-empty и --retry-unresolved используйте отдельными запусками."))

    if options.resolve_until_empty and options.resolve_offset > 0 and not options.retry_unresolved:
        raise CommandError(
            _("--resolve-until-empty используйте без --resolve-offset (для нового прохода offset не нужен).")
        )
