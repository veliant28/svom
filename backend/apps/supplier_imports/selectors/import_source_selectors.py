from __future__ import annotations

from pathlib import Path

from django.conf import settings

from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportSource


def get_import_source_by_code(code: str) -> ImportSource:
    return ImportSource.objects.select_related("supplier").get(code=code)


def get_active_import_sources():
    return ImportSource.objects.filter(is_active=True).select_related("supplier").order_by("name")


def ensure_default_import_sources() -> dict[str, ImportSource]:
    utr_path, gpl_path = _resolve_default_source_paths()

    defaults = {
        "utr": {
            "name": "UTR",
            "parser_type": ImportSource.PARSER_UTR,
            "path": utr_path,
            "supplier_name": "UTR",
            "supplier_code": "utr",
        },
        "gpl": {
            "name": "GPL",
            "parser_type": ImportSource.PARSER_GPL,
            "path": gpl_path,
            "supplier_name": "GPL",
            "supplier_code": "gpl",
        },
    }

    result: dict[str, ImportSource] = {}
    for code, config in defaults.items():
        supplier, _ = Supplier.objects.get_or_create(
            code=config["supplier_code"],
            defaults={
                "name": config["supplier_name"],
                "is_active": True,
            },
        )

        existing_source = ImportSource.objects.filter(code=code).first()
        existing_input_path = (existing_source.input_path or "").strip() if existing_source else ""
        input_path = existing_input_path if _is_existing_path(existing_input_path) else config["path"]

        source, _ = ImportSource.objects.update_or_create(
            code=code,
            defaults={
                "name": config["name"],
                "supplier": supplier,
                "parser_type": config["parser_type"],
                "input_path": input_path,
                "file_patterns": ["*.xlsx", "*.json", "*.csv", "*.txt", "*.xml", "*.yml", "*.yaml"],
                "default_currency": "UAH",
                "auto_reprice_after_import": True,
                "auto_reindex_after_import": False,
                "schedule_timezone": "Europe/Kyiv",
                "is_active": True,
            },
        )
        result[code] = source

    return result


def _resolve_default_source_paths() -> tuple[str, str]:
    roots = _candidate_roots()

    utr_candidates: list[Path] = []
    gpl_candidates: list[Path] = []
    for root in roots:
        utr_candidates.extend(item for item in root.glob("utr*price*.xlsx") if item.is_file())
        utr_candidates.extend(item for item in root.glob("*utr*.xlsx") if item.is_file())
        gpl_candidates.extend(item for item in root.glob("price_gpl*.xlsx") if item.is_file())
        gpl_candidates.extend(item for item in root.glob("*gpl*.xlsx") if item.is_file())

    if utr_candidates:
        utr_candidates.sort()
        utr_path = str(utr_candidates[-1])
    else:
        utr_dir = next((root / "UTR" for root in roots if (root / "UTR").exists()), roots[0] / "UTR")
        utr_path = str(utr_dir)

    if gpl_candidates:
        gpl_candidates.sort()
        gpl_path = str(gpl_candidates[-1])
    else:
        gpl_file = next((root / "GPL.xlsx" for root in roots if (root / "GPL.xlsx").exists()), roots[0] / "GPL.xlsx")
        gpl_path = str(gpl_file)

    return utr_path, gpl_path


def _candidate_roots() -> list[Path]:
    candidates = [
        Path(getattr(settings, "ROOT_DIR", "") or "").expanduser(),
        Path(getattr(settings, "BASE_DIR", "") or "").expanduser(),
        Path.cwd().expanduser(),
        Path("/app"),
        Path("/Users/vs/Django/svom"),
    ]
    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            normalized = candidate.resolve()
        except OSError:
            normalized = candidate
        key = str(normalized)
        if not key or key in seen:
            continue
        seen.add(key)
        if normalized.exists():
            roots.append(normalized)
    if roots:
        return roots
    return [Path(getattr(settings, "ROOT_DIR", ".")).expanduser()]


def _is_existing_path(raw_path: str) -> bool:
    if not raw_path:
        return False
    return Path(raw_path).expanduser().exists()
