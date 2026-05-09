from __future__ import annotations

from dataclasses import dataclass


STATUS_ACTIVE = "active"
STATUS_REVIEW = "review"
STATUS_IGNORED = "ignored"


@dataclass(frozen=True)
class SupplierCategoryMappingRecord:
    supplier_code: str
    raw_category: str
    raw_group: str
    target_category_slug: str
    status: str
    confidence: float
    note: str
    source: str = "manual"


@dataclass(frozen=True)
class SupplierCategorySuggestion:
    target_category_slug: str
    target_category_name: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class SupplierCategoryResolution:
    target_category_slug: str
    status: str
    confidence: float
    reason: str
    source: str


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


# Controlled manual mapping layer (config-first, no auto category creation).
_MAPPING_ROWS: tuple[SupplierCategoryMappingRecord, ...] = (
    SupplierCategoryMappingRecord(
        supplier_code="gpl",
        raw_category="AdBlue",
        raw_group="*",
        target_category_slug="adblue-i-tekhnicheskie-zhidkosti",
        status=STATUS_ACTIVE,
        confidence=0.91,
        note="manual_confirmed_adblue_mapping",
    ),
    SupplierCategoryMappingRecord(
        supplier_code="gpl",
        raw_category="Ізоляційні стрічки",
        raw_group="*",
        target_category_slug="izolenta-i-elektromaterialy",
        status=STATUS_ACTIVE,
        confidence=0.92,
        note="manual_confirmed_tape_mapping",
    ),
)


CATEGORY_NAME_BY_SLUG = {
    "adblue-i-tekhnicheskie-zhidkosti": "AdBlue и технические жидкости",
    "izolenta-i-elektromaterialy": "Изолента и электроматериалы",
    "motornye-masla": "Моторные масла",
    "transmissionnye-masla": "Трансмиссионные масла",
    "gidravlicheskie-masla": "Гидравлические масла",
    "tekhnicheskie-zhidkosti": "Технические жидкости",
    "antifrizy-i-okhlazhdaiushchie-zhidkosti": "Антифризы и охлаждающие жидкости",
    "tormoznye-zhidkosti": "Тормозные жидкости",
}


CONTROLLED_SUPPLIER_TARGET_SLUGS = frozenset(CATEGORY_NAME_BY_SLUG)


_ENGINE_OIL_TOKENS = (
    "motor oil",
    "engine oil",
    "моторне",
    "моторное",
    "моторна олива",
    "моторное масло",
    "0w-20",
    "0w20",
    "0w 20",
    "0w-30",
    "0w30",
    "0w 30",
    "0w-40",
    "0w40",
    "0w 40",
    "5w-20",
    "5w20",
    "5w 20",
    "5w-30",
    "5w30",
    "5w 30",
    "5w-40",
    "5w40",
    "5w 40",
    "10w-30",
    "10w30",
    "10w 30",
    "10w-40",
    "10w40",
    "10w 40",
    "15w-40",
    "15w40",
    "15w 40",
    "helix",
    "hightronic",
    "bluetronic",
    "supertronic",
    "turboral",
    " elite ",
)


_HYDRAULIC_OIL_TOKENS = (
    "hydraulic oil",
    "hydraulic",
    "гідравл",
    "гидравл",
    "hlp",
    "iso-l-hm",
)

_TRANSMISSION_WEAK_TOKENS = (
    "transmission",
    "трансміс",
    "трансмис",
    "getriebe",
)

_TRANSMISSION_STRONG_TOKENS = (
    "atf",
    "dexron",
    "gl-4",
    "gl4",
    "gl-5",
    "gl5",
    "75w-80",
    "75w80",
    "75w-90",
    "75w90",
    "80w-90",
    "80w90",
    "85w-140",
    "85w140",
    "gear oil",
    "matic",
)

_OIL_FLUID_CONTEXT_TOKENS = (
    "oil",
    "олив",
    "масл",
    "мастил",
    "lubricant",
    "fluid",
    "рідина",
    "жидкост",
    "atf",
    "dexron",
    "antifreeze",
    "coolant",
    "adblue",
    "dot",
    "hlp",
    "iso-l-hm",
)


_TECHNICAL_FLUID_TOKENS = (
    "technical fluid",
    "технічна рідина",
    "техническая жидкость",
    "service fluid",
)

_WASHER_FLUID_TOKENS = (
    "омивач",
    "омывател",
    "склоомивач",
    "стеклоомывател",
    "washer fluid",
    "windshield washer",
    "screenwash",
    "screen wash",
)

_WASHER_PART_TOKENS = (
    "форсун",
    "насос",
    "бачок",
    "моторчик",
    "щітк",
    "щетк",
    "трапец",
)


_ADBLUE_TOKENS = (
    "adblue",
    "euroblue",
    "def",
    "urea",
    "сечовин",
    "мочевин",
)


_COOLANT_TOKENS = (
    "antifreeze",
    "coolant",
    "антифриз",
    "тосол",
)

_COOLANT_WEAK_TOKENS = (
    "охолодж",
    "охлажд",
)

_COOLANT_FLUID_CONTEXT_TOKENS = (
    "рідина",
    "жидкост",
    "fluid",
    "концентрат",
    "premix",
    "g11",
    "g12",
    "g13",
)

_COOLANT_PART_TOKENS = (
    "датчик",
    "sensor",
    "вентилятор",
    "fan",
    "радіатор",
    "радиатор",
    "патруб",
    "термостат",
    "насос",
    "помпа",
    "прокладк",
    "корпус",
    "муфт",
)


_BRAKE_FLUID_TOKENS = (
    "brake fluid",
    "гальмівна рідина",
    "тормозная жидкость",
    "dot 3",
    "dot-3",
    "dot 4",
    "dot-4",
    "dot 5.1",
    "dot-5.1",
)


_BRAND_ONLY_GROUP_MARKERS = frozenset(
    {
        "aral",
        "evo",
        "repsol",
        "shell",
        "oe vw audi",
        "oe toyota",
        "bmw",
        "total",
        "hico",
        "vira",
        "organic prink",
    }
)


class SupplierCategoryMappingResolver:
    def resolve(self, *, supplier_code: str, raw_category: str, raw_group: str) -> SupplierCategoryMappingRecord | None:
        supplier_norm = _norm(supplier_code)
        category_norm = _norm(raw_category)
        group_norm = _norm(raw_group)

        exact: SupplierCategoryMappingRecord | None = None
        wildcard: SupplierCategoryMappingRecord | None = None
        for row in _MAPPING_ROWS:
            if _norm(row.supplier_code) != supplier_norm:
                continue
            if _norm(row.raw_category) != category_norm:
                continue
            row_group = _norm(row.raw_group)
            if row_group == group_norm:
                exact = row
                break
            if row_group in {"", "*"}:
                wildcard = row
        return exact or wildcard

    def resolve_with_evidence(
        self,
        *,
        supplier_code: str,
        raw_category: str,
        raw_group: str,
        raw_name: str,
        raw_description: str,
        product_name: str,
        supplier_product_name: str,
        raw_brand: str,
    ) -> SupplierCategoryResolution | None:
        mapping = self.resolve(supplier_code=supplier_code, raw_category=raw_category, raw_group=raw_group)
        if mapping is not None:
            return SupplierCategoryResolution(
                target_category_slug=mapping.target_category_slug,
                status=mapping.status,
                confidence=float(mapping.confidence),
                reason=mapping.note,
                source="explicit_mapping",
            )

        evidence = build_evidence_text(
            product_name,
            supplier_product_name,
            raw_category,
            raw_group,
            raw_name,
            raw_description,
            raw_brand,
        )
        return self._infer_controlled_mapping(
            supplier_code=supplier_code,
            raw_category=raw_category,
            raw_group=raw_group,
            raw_brand=raw_brand,
            evidence_text=evidence,
        )

    def infer_existing_target(self, *, evidence_text: str) -> SupplierCategorySuggestion | None:
        # Backward-compatible helper for read-only suggestions.
        inferred = self._infer_controlled_mapping(
            supplier_code="gpl",
            raw_category="",
            raw_group="",
            raw_brand="",
            evidence_text=evidence_text,
        )
        if inferred is None or inferred.status != STATUS_ACTIVE:
            return None
        return SupplierCategorySuggestion(
            target_category_slug=inferred.target_category_slug,
            target_category_name=CATEGORY_NAME_BY_SLUG.get(inferred.target_category_slug, inferred.target_category_slug),
            confidence=inferred.confidence,
            reason=inferred.reason,
        )

    def _infer_controlled_mapping(
        self,
        *,
        supplier_code: str,
        raw_category: str,
        raw_group: str,
        raw_brand: str,
        evidence_text: str,
    ) -> SupplierCategoryResolution | None:
        if _norm(supplier_code) != "gpl":
            return None

        category_norm = _norm(raw_category)
        group_norm = _norm(raw_group)
        brand_norm = _norm(raw_brand)
        text_norm = _norm(evidence_text)
        text = f" {text_norm} "
        if not text_norm:
            return None

        has_oil_context = _contains_any(text, _OIL_FLUID_CONTEXT_TOKENS)
        transmission_has_strong_signal = _contains_any(text, _TRANSMISSION_STRONG_TOKENS)
        transmission_has_weak_signal = _contains_any(text, _TRANSMISSION_WEAK_TOKENS)
        hydraulic_has_signal = _contains_any(text, _HYDRAULIC_OIL_TOKENS)
        washer_has_signal = _contains_any(text, _WASHER_FLUID_TOKENS)
        washer_has_part_signal = _contains_any(text, _WASHER_PART_TOKENS)
        coolant_has_strong_signal = _contains_any(text, _COOLANT_TOKENS)
        coolant_has_weak_signal = _contains_any(text, _COOLANT_WEAK_TOKENS)
        coolant_has_fluid_context = _contains_any(text, _COOLANT_FLUID_CONTEXT_TOKENS)
        coolant_has_part_signal = _contains_any(text, _COOLANT_PART_TOKENS)
        coolant_signal = coolant_has_strong_signal or (coolant_has_weak_signal and coolant_has_fluid_context)

        signal_map = {
            "motornye-masla": _contains_any(text, _ENGINE_OIL_TOKENS),
            "transmissionnye-masla": transmission_has_strong_signal
            or (transmission_has_weak_signal and has_oil_context),
            "gidravlicheskie-masla": hydraulic_has_signal and has_oil_context,
            "tekhnicheskie-zhidkosti": _contains_any(text, _TECHNICAL_FLUID_TOKENS),
            "adblue-i-tekhnicheskie-zhidkosti": _contains_any(text, _ADBLUE_TOKENS),
            "antifrizy-i-okhlazhdaiushchie-zhidkosti": coolant_signal,
            "tormoznye-zhidkosti": _contains_any(text, _BRAKE_FLUID_TOKENS),
        }

        primary_hits = [
            slug
            for slug in (
                "motornye-masla",
                "transmissionnye-masla",
                "gidravlicheskie-masla",
                "adblue-i-tekhnicheskie-zhidkosti",
                "antifrizy-i-okhlazhdaiushchie-zhidkosti",
                "tormoznye-zhidkosti",
            )
            if signal_map[slug]
        ]

        has_technical_signal = signal_map["tekhnicheskie-zhidkosti"]
        has_brand_only_marker = category_norm in _BRAND_ONLY_GROUP_MARKERS or group_norm in _BRAND_ONLY_GROUP_MARKERS
        has_brand_marker = has_brand_only_marker or brand_norm in _BRAND_ONLY_GROUP_MARKERS

        if len(primary_hits) > 1:
            return SupplierCategoryResolution(
                target_category_slug="",
                status=STATUS_REVIEW,
                confidence=0.72,
                reason="ambiguous_multi_fluid_signal",
                source="inferred_mapping_v2",
            )

        if len(primary_hits) == 1:
            slug = primary_hits[0]
            if slug == "adblue-i-tekhnicheskie-zhidkosti":
                return SupplierCategoryResolution(
                    target_category_slug=slug,
                    status=STATUS_ACTIVE,
                    confidence=0.97,
                    reason="adblue_signal",
                    source="inferred_mapping_v2",
                )
            if (
                slug == "antifrizy-i-okhlazhdaiushchie-zhidkosti"
                and coolant_has_part_signal
                and not coolant_has_strong_signal
            ):
                return SupplierCategoryResolution(
                    target_category_slug="",
                    status=STATUS_REVIEW,
                    confidence=0.7,
                    reason="cooling_system_part_not_fluid",
                    source="inferred_mapping_v2",
                )

            reason = {
                "motornye-masla": "engine_oil_signal",
                "transmissionnye-masla": "transmission_oil_signal",
                "gidravlicheskie-masla": "hydraulic_oil_signal",
                "antifrizy-i-okhlazhdaiushchie-zhidkosti": "coolant_signal",
                "tormoznye-zhidkosti": "brake_fluid_signal",
            }[slug]
            return SupplierCategoryResolution(
                target_category_slug=slug,
                status=STATUS_ACTIVE,
                confidence=0.95,
                reason=reason,
                source="inferred_mapping_v2",
            )

        if has_technical_signal:
            return SupplierCategoryResolution(
                target_category_slug="tekhnicheskie-zhidkosti",
                status=STATUS_ACTIVE,
                confidence=0.9,
                reason="technical_fluid_signal",
                source="inferred_mapping_v2",
            )

        if washer_has_signal and not washer_has_part_signal:
            return SupplierCategoryResolution(
                target_category_slug="tekhnicheskie-zhidkosti",
                status=STATUS_ACTIVE,
                confidence=0.93,
                reason="washer_fluid_signal",
                source="inferred_mapping_v2",
            )

        if has_brand_only_marker and not any(signal_map.values()):
            return SupplierCategoryResolution(
                target_category_slug="",
                status=STATUS_REVIEW,
                confidence=0.63,
                reason="brand_only_without_fluid_signal",
                source="inferred_mapping_v2",
            )

        if has_brand_marker and not any(signal_map.values()):
            return SupplierCategoryResolution(
                target_category_slug="",
                status=STATUS_REVIEW,
                confidence=0.6,
                reason="brand_without_fluid_signal",
                source="inferred_mapping_v2",
            )

        return None


def build_evidence_text(*parts: str) -> str:
    return " ".join(part.strip() for part in parts if str(part or "").strip())


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)
