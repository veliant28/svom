from __future__ import annotations

from dataclasses import dataclass


PAINT_POSITIVE_TOKENS = (
    "емаль",
    "эмаль",
    "фарба",
    "краска",
    "лак",
    "грунт",
    "primer",
    "varnish",
    "paint",
    "aerosol",
    "аерозоль",
    "аэрозоль",
)

ABRASIVE_TOKENS = (
    "круг",
    "наждач",
    "шлиф",
    "абразив",
)

PPE_TOKENS = (
    "комбинезон",
    "комбінезон",
    "очки",
    "окуляри",
    "перчатки",
    "рукавички",
    "защит",
    "спецодежда",
    "workwear",
)

PAPER_TAPE_TOKENS = (
    "бумага",
    "папір",
    "sponge",
    "губка",
    "салфетка",
    "серветка",
    "малярная лента",
    "стрічка",
    "masking tape",
    "лента",
)

TOOLS_ACCESSORIES_TOKENS = (
    "инструмент",
    "інструмент",
    "аксессуар",
    "аксесуар",
)


@dataclass(frozen=True)
class ContaminationDecision:
    status: str
    confidence: float
    reason: str


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def classify_manual_category_contamination(*, text: str) -> ContaminationDecision:
    normalized = _norm(text)
    if not normalized:
        return ContaminationDecision("needs_review", 0.5, "empty_evidence")

    has_positive = _contains_any(normalized, PAINT_POSITIVE_TOKENS)
    has_abrasive = _contains_any(normalized, ABRASIVE_TOKENS)
    has_ppe = _contains_any(normalized, PPE_TOKENS)
    has_paper = _contains_any(normalized, PAPER_TAPE_TOKENS)
    has_tools = _contains_any(normalized, TOOLS_ACCESSORIES_TOKENS)

    negatives = [has_abrasive, has_ppe, has_paper, has_tools]

    if has_positive and not any(negatives):
        return ContaminationDecision("safe_paint", 0.95, "positive_paint_signal")

    if has_abrasive:
        return ContaminationDecision("should_move_to_abrasives", 0.93, "abrasive_signal")

    if has_ppe:
        return ContaminationDecision("should_move_to_ppe_safety", 0.92, "ppe_or_workwear_signal")

    if has_paper:
        return ContaminationDecision("should_move_to_paper_tape_consumables", 0.92, "paper_tape_consumables_signal")

    if has_tools:
        return ContaminationDecision("should_move_to_tools_accessories", 0.9, "tools_accessories_signal")

    if has_positive and any(negatives):
        return ContaminationDecision("needs_review", 0.7, "mixed_positive_and_negative_signal")

    return ContaminationDecision("needs_review", 0.62, "no_paint_signal")
