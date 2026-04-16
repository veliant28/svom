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
    root_dir = Path(settings.ROOT_DIR)
    utr_candidates = sorted(root_dir.glob("utr*price*.xlsx"))
    gpl_candidates = sorted(root_dir.glob("price_gpl*.xlsx"))

    utr_path = str(utr_candidates[-1]) if utr_candidates else str(root_dir / "UTR")
    gpl_path = str(gpl_candidates[-1]) if gpl_candidates else str(root_dir / "GPL.txt")

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

        source, _ = ImportSource.objects.update_or_create(
            code=code,
            defaults={
                "name": config["name"],
                "supplier": supplier,
                "parser_type": config["parser_type"],
                "input_path": config["path"],
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
