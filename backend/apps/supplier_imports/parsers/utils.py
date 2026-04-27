from __future__ import annotations

import csv
import io
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from typing import Any


def normalize_article(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def normalize_brand(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    raw = str(value).strip().replace(" ", "")
    if not raw:
        return None

    normalized = raw.replace(",", ".")
    normalized = re.sub(r"[^0-9.\-]", "", normalized)
    if not normalized:
        return None

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def parse_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    raw = str(value).strip()
    if not raw:
        return 0

    raw = raw.replace(" ", "")
    raw = raw.replace(",", ".")

    if raw.startswith(">"):
        raw = raw[1:]

    match = re.search(r"-?\d+(?:\.\d+)?", raw)
    if not match:
        return 0

    try:
        return int(float(match.group(0)))
    except ValueError:
        return 0


def detect_delimiter(sample: str) -> str:
    candidates = [",", ";", "\t", "|"]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(candidates))
        return dialect.delimiter
    except csv.Error:
        pass

    best = ","
    best_score = -1
    for candidate in candidates:
        score = sample.count(candidate)
        if score > best_score:
            best = candidate
            best_score = score
    return best


def parse_table_rows(content: str) -> list[tuple[int, dict[str, str]]]:
    sample = content[:4000]
    delimiter = detect_delimiter(sample)

    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    rows: list[tuple[int, dict[str, str]]] = []
    for index, row in enumerate(reader, start=2):
        cleaned = {str(key).strip(): (value.strip() if isinstance(value, str) else value) for key, value in row.items() if key}
        if any((value or "").strip() for value in cleaned.values() if isinstance(value, str)):
            rows.append((index, cleaned))
    return rows


_XLSX_NS = {
    "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}
_XLSX_MAIN_NS = _XLSX_NS["x"]
_XLSX_ROW_TAG = f"{{{_XLSX_MAIN_NS}}}row"
_XLSX_CELL_TAG = f"{{{_XLSX_MAIN_NS}}}c"
_XLSX_VALUE_TAG = f"{{{_XLSX_MAIN_NS}}}v"
_XLSX_INLINE_STRING_TAG = f"{{{_XLSX_MAIN_NS}}}is"
_XLSX_TEXT_TAG = f"{{{_XLSX_MAIN_NS}}}t"


def _column_index(cell_ref: str) -> int:
    value = 0
    for char in cell_ref:
        if not char.isalpha():
            break
        char = char.upper()
        value = (value * 26) + (ord(char) - ord("A") + 1)
    return max(value - 1, 0)


def parse_xlsx_rows(file_path: Path) -> list[tuple[int, dict[str, str]]]:
    with ZipFile(file_path) as archive:
        workbook_xml = ET.fromstring(archive.read("xl/workbook.xml"))
        rels_xml = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_xml.findall("p:Relationship", _XLSX_NS)
            if rel.attrib.get("Id") and rel.attrib.get("Target")
        }

        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_xml = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_xml.findall("x:si", _XLSX_NS):
                text = "".join(node.text or "" for node in item.findall(".//x:t", _XLSX_NS))
                shared_strings.append(text)

        first_sheet = workbook_xml.find("x:sheets/x:sheet", _XLSX_NS)
        if first_sheet is None:
            return []

        relation_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        if not relation_id:
            return []

        sheet_target = rel_map.get(relation_id)
        if not sheet_target:
            return []
        sheet_target = sheet_target.lstrip("/")
        if not sheet_target.startswith("xl/"):
            sheet_target = f"xl/{sheet_target}"

        sheet_xml = ET.fromstring(archive.read(sheet_target))

        unique_headers: list[str] | None = None
        result: list[tuple[int, dict[str, str]]] = []

        for fallback_row_number, row_xml in enumerate(sheet_xml.iter(_XLSX_ROW_TAG), start=1):
            row_number = int(row_xml.attrib.get("r", str(fallback_row_number)))
            row_values: dict[int, str] = {}
            max_index = 0

            for cell in row_xml:
                if cell.tag != _XLSX_CELL_TAG:
                    continue

                ref = cell.attrib.get("r", "")
                index = _column_index(ref)
                max_index = max(max_index, index)

                cell_type = cell.attrib.get("t")
                value_text = ""
                inline_node = None
                for child in cell:
                    if child.tag == _XLSX_VALUE_TAG:
                        value_text = child.text or ""
                    elif child.tag == _XLSX_INLINE_STRING_TAG:
                        inline_node = child

                value = ""
                if cell_type == "s" and value_text:
                    shared_index = int(value_text)
                    if 0 <= shared_index < len(shared_strings):
                        value = shared_strings[shared_index]
                elif cell_type == "inlineStr" and inline_node is not None:
                    value = "".join(node.text or "" for node in inline_node.iter(_XLSX_TEXT_TAG))
                else:
                    value = value_text

                row_values[index] = value.strip()

            if unique_headers is None:
                header_values = [row_values.get(index, "") for index in range(max_index + 1)]
                unique_headers = _unique_headers(header_values)
                continue

            row = {header: row_values.get(index, "") for index, header in enumerate(unique_headers)}
            if any(value.strip() for value in row.values()):
                result.append((row_number, row))

        if unique_headers is None:
            return []

        return result


def _unique_headers(header_values: list[str]) -> list[str]:
    headers = [_header or f"column_{idx + 1}" for idx, _header in enumerate(header_values)]

    unique_headers: list[str] = []
    seen_headers: dict[str, int] = {}
    for header in headers:
        normalized = header.strip() or "column"
        count = seen_headers.get(normalized, 0)
        seen_headers[normalized] = count + 1
        unique_headers.append(normalized if count == 0 else f"{normalized}_{count + 1}")
    return unique_headers


def rows_to_csv_content(rows: list[tuple[int, dict[str, str]]]) -> str:
    if not rows:
        return ""
    headers = list(rows[0][1].keys())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for _, row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def extract_json_payloads(content: str) -> list[Any]:
    payloads: list[Any] = []
    try:
        payloads.append(json.loads(content))
        return payloads
    except json.JSONDecodeError:
        pass

    start: int | None = None
    stack: list[str] = []
    in_string = False
    escape = False

    for index, char in enumerate(content):
        if start is None:
            if char in "[{":
                start = index
                stack = [char]
                in_string = False
                escape = False
            continue

        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char in "[{":
            stack.append(char)
            continue

        if char in "]}":
            if not stack:
                start = None
                continue

            opener = stack[-1]
            if (opener == "{" and char == "}") or (opener == "[" and char == "]"):
                stack.pop()
            else:
                start = None
                stack = []
                continue

            if not stack and start is not None:
                candidate = content[start : index + 1]
                start = None
                try:
                    payload = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                payloads.append(payload)

    return payloads


def extract_value(row: dict[str, Any], field_names: list[str]) -> Any:
    for field_name in field_names:
        if field_name in row:
            return row.get(field_name)

    lowered = {key.lower(): key for key in row.keys()}
    for field_name in field_names:
        lookup = lowered.get(field_name.lower())
        if lookup is not None:
            return row.get(lookup)
    return None


def resolve_field_names(mapping_config: dict[str, Any], key: str, defaults: list[str]) -> list[str]:
    raw = mapping_config.get(key)
    if raw is None:
        return defaults
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        result = [str(item) for item in raw if item]
        return result or defaults
    return defaults
