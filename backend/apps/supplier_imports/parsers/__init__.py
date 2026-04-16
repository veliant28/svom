from apps.supplier_imports.parsers.base import ParseIssue, ParsedOffer, ParseResult, ParserContext, SupplierOfferParser
from apps.supplier_imports.parsers.gpl_parser import GPLParser
from apps.supplier_imports.parsers.utr_parser import UTRParser

PARSER_REGISTRY: dict[str, SupplierOfferParser] = {
    UTRParser.parser_code: UTRParser(),
    GPLParser.parser_code: GPLParser(),
}


def get_parser(parser_code: str) -> SupplierOfferParser:
    parser = PARSER_REGISTRY.get(parser_code)
    if parser is None:
        raise ValueError(f"Unsupported parser: {parser_code}")
    return parser


__all__ = [
    "ParseIssue",
    "ParsedOffer",
    "ParseResult",
    "ParserContext",
    "SupplierOfferParser",
    "UTRParser",
    "GPLParser",
    "get_parser",
]
