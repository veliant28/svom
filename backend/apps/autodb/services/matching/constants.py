from __future__ import annotations

IMAGES_DISABLED_REASON = "Auto_DB images disabled until thumbnail preview/guard exists"
REMOTE_QUOTA_KEY = "autodb_pro_mysql"

DETERMINISTIC_TABLES = ("article_numbers", "articles")
CLONE_SYNC_TABLES = (
    "article_numbers",
    "articles",
    "article_prd",
    "prd",
    "article_inf",
    "article_attributes",
    "article_li",
)
DISABLED_TABLES = ("article_images",)

NON_TECDOC_BRAND_KEYS = {
    "OE",
    "OEM",
    "ORIGINAL",
    "GENUINE",
    "NONAME",
    "NO NAME",
    "USED",
    "БУ",
    "Б/У",
    "ОРИГИНАЛ",
    # Supplier-only / non-TecDoc brands from GPL streams.
    "AT",
    "K2",
    "LSA",
    "MITKA",
    "DAINTON",
    "ТМК",
    "LAVITA",
    "VIRA",
    "CS SYSTEM",
    "ELEGANT",
    "БЕЗ БРЕНДУ",
    "MOL",
    "XADO",
    "LOTOS",
    "HELPIX",
    "HI-GEAR",
    "TURTLE WAX",
    "TOTALENERGIES",
    "DOLONI",
    "YATO",
    "NANO5",
    "MR.BUILD",
    "VERYLUBE",
    "DOCTOR WAX",
    "DONE DEAL",
    "STEEL POWER",
    "VOIN",
    "SMIRDEX",
    "VIROK",
    "NOVVIC",
    "STEP UP",
    "NANOX",
    "ANY WAY",
    "ATAMAN",
    "ASIA360",
}

INVALID_BRAND_VALUE_KEYS = {
    "",
    "-",
    "--",
    "N/A",
    "NA",
    "NONE",
    "NULL",
    "UNKNOWN",
    "УГОРЩИНА",
    "УДАЛЕННЫЕ",
}

UNSAFE_BRAND_KEYS = {
    # CTR exists in several real-world catalog/vendor forms; require a manual mapping.
    "CTR",
}

BUILTIN_SAFE_ALIASES = {
    "LEMFORDER": "LEMFORDER",
    "LEMFÖRDER": "LEMFORDER",
    "LEMFORDERGMBH": "LEMFORDER",
    "WIX": "WIXFILTERS",
    "WIXFILTER": "WIXFILTERS",
    "WIXFILTERS": "WIXFILTERS",
}
