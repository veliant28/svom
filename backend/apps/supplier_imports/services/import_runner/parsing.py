from __future__ import annotations

from pathlib import Path

from apps.supplier_imports.models import ImportArtifact, ImportSource
from apps.supplier_imports.parsers import ParseResult, ParserContext
from apps.supplier_imports.parsers.utils import parse_xlsx_rows, rows_to_csv_content


def parse_artifact(*, source: ImportSource, artifact: ImportArtifact, parser) -> ParseResult:
    file_path = Path(artifact.file_path)
    if file_path.suffix.lower() == ".xlsx":
        rows = parse_xlsx_rows(file_path)
        content = rows_to_csv_content(rows)
    else:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    context = ParserContext(
        source_code=source.code,
        mapping_config=source.mapping_config,
        default_currency=source.default_currency,
    )

    parse_result = parser.parse_content(content, file_name=artifact.file_name, context=context)
    artifact.parsed_rows = len(parse_result.offers)
    artifact.errors_count = len(parse_result.issues)
    artifact.status = ImportArtifact.STATUS_PROCESSED if parse_result.offers else ImportArtifact.STATUS_SKIPPED
    if parse_result.issues and not parse_result.offers:
        artifact.status = ImportArtifact.STATUS_FAILED
    artifact.save(update_fields=("parsed_rows", "errors_count", "status", "updated_at"))
    return parse_result
