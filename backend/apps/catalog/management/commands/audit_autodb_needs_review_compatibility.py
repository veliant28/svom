from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.services.autodb_link_compatibility import evaluate_category_compatibility


_MANUAL_REVIEW_RAW_CATEGORY_TOKENS = (
    "датчик",
    "датчики",
    "проклад",
    "комплектуюч",
    "комплектующ",
    "пильовик",
    "пильовики",
    "подшип",
    "підшип",
)


def _to_float(value: str) -> float:
    try:
        return float(str(value or "").strip() or 0.0)
    except Exception:
        return 0.0


def _norm(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


class Command(BaseCommand):
    help = "Read-only needs_review compatibility audit from Auto-DB GPL candidate CSV."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True)
        parser.add_argument("--candidates-csv", type=str, required=True)
        parser.add_argument("--export-csv", type=str, required=True)
        parser.add_argument("--summary-csv", type=str, required=True)

    def handle(self, *args, **options):
        supplier = str(options.get("supplier") or "").strip().lower()
        if supplier != "gpl":
            raise CommandError("This audit currently supports only --supplier GPL.")

        candidates_csv = Path(str(options.get("candidates_csv") or "").strip()).expanduser()
        export_csv = Path(str(options.get("export_csv") or "").strip()).expanduser()
        summary_csv = Path(str(options.get("summary_csv") or "").strip()).expanduser()
        if not candidates_csv.exists():
            raise CommandError(f"Candidates CSV not found: {candidates_csv}")

        rows_out: list[dict[str, str]] = []
        summary_counter = Counter()
        proposed_counter = Counter()

        with candidates_csv.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if str(row.get("decision") or "").strip() != "needs_review":
                    continue

                raw_category = str(row.get("raw_category") or "")
                raw_group = str(row.get("raw_group") or "")
                mapped_site_category = str(row.get("mapped_site_category") or "")
                candidate_group = str(row.get("candidate_autodb_group") or "")
                candidate_title = str(row.get("candidate_autodb_title") or "")
                current_reason = str(row.get("reason") or "")
                blocker_type = str(row.get("blocker_type") or "")
                semantic_score = _to_float(str(row.get("semantic_score") or "0"))
                brand_score = _to_float(str(row.get("brand_match_score") or "0"))
                article_score = _to_float(str(row.get("article_match_score") or "0"))

                compatibility_score, compatibility_rule = evaluate_category_compatibility(
                    raw_category=raw_category,
                    raw_group=raw_group,
                    mapped_site_category=mapped_site_category,
                    candidate_group=candidate_group,
                    candidate_title=candidate_title,
                )

                proposed_decision = "keep_needs_review"
                proposed_rule = compatibility_rule
                confidence = compatibility_score
                explanation = "compatibility_signal_insufficient"

                if semantic_score < 0.999:
                    proposed_decision = "semantic_conflict"
                    proposed_rule = "semantic_blocker"
                    confidence = 1.0 - semantic_score
                    explanation = "semantic_score_below_1"
                elif not mapped_site_category.strip():
                    proposed_decision = "manual_review_only"
                    proposed_rule = "missing_site_category"
                    confidence = 0.95
                    explanation = "mapped_site_category_empty"
                elif _contains_manual_review_tokens(raw_category):
                    proposed_decision = "manual_review_only"
                    proposed_rule = "manual_review_bucket"
                    confidence = 0.9
                    explanation = "generic_mixed_raw_category"
                elif (
                    blocker_type == "category_compatibility_mismatch"
                    and brand_score >= 0.8
                    and article_score >= 0.95
                    and compatibility_score >= 0.7
                ):
                    proposed_decision = "can_promote_to_safe"
                    proposed_rule = compatibility_rule
                    confidence = max(0.91, compatibility_score)
                    explanation = "exact_article_brand_plus_safe_compatibility_equivalence"

                out = {
                    "product_id": str(row.get("product_id") or ""),
                    "raw_brand": str(row.get("raw_brand") or ""),
                    "raw_td_article": str(row.get("gpl_td_article") or ""),
                    "raw_name": str(row.get("raw_name") or ""),
                    "raw_category": raw_category,
                    "raw_group": raw_group,
                    "mapped_site_category": mapped_site_category,
                    "candidate_autodb_supplier_id": str(row.get("candidate_autodb_supplier_id") or ""),
                    "candidate_autodb_article_number": str(row.get("candidate_autodb_article_number") or ""),
                    "candidate_autodb_title": candidate_title,
                    "candidate_autodb_group": candidate_group,
                    "current_reason": current_reason,
                    "blocker_type": blocker_type,
                    "semantic_score": f"{semantic_score:.3f}",
                    "category_compatibility_score": f"{compatibility_score:.3f}",
                    "proposed_decision": proposed_decision,
                    "proposed_rule": proposed_rule,
                    "confidence": f"{confidence:.3f}",
                    "explanation": explanation,
                }
                rows_out.append(out)
                proposed_counter[proposed_decision] += 1

                summary_key = (
                    out["raw_brand"],
                    out["mapped_site_category"],
                    f'{out["raw_category"]} | {out["raw_group"]}',
                    out["candidate_autodb_group"],
                    out["current_reason"],
                    out["blocker_type"],
                    out["proposed_decision"],
                    out["proposed_rule"],
                )
                summary_counter[summary_key] += 1

        export_csv.parent.mkdir(parents=True, exist_ok=True)
        with export_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "product_id",
                    "raw_brand",
                    "raw_td_article",
                    "raw_name",
                    "raw_category",
                    "raw_group",
                    "mapped_site_category",
                    "candidate_autodb_supplier_id",
                    "candidate_autodb_article_number",
                    "candidate_autodb_title",
                    "candidate_autodb_group",
                    "current_reason",
                    "blocker_type",
                    "semantic_score",
                    "category_compatibility_score",
                    "proposed_decision",
                    "proposed_rule",
                    "confidence",
                    "explanation",
                ],
            )
            writer.writeheader()
            writer.writerows(rows_out)

        summary_csv.parent.mkdir(parents=True, exist_ok=True)
        with summary_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "raw_brand",
                    "mapped_site_category",
                    "raw_category_raw_group",
                    "candidate_autodb_group",
                    "current_reason",
                    "blocker_type",
                    "proposed_decision",
                    "proposed_rule",
                    "count",
                ],
            )
            writer.writeheader()
            for (
                raw_brand,
                mapped_site_category,
                raw_category_raw_group,
                candidate_autodb_group,
                current_reason,
                blocker_type,
                proposed_decision,
                proposed_rule,
            ), count in summary_counter.most_common():
                writer.writerow(
                    {
                        "raw_brand": raw_brand,
                        "mapped_site_category": mapped_site_category,
                        "raw_category_raw_group": raw_category_raw_group,
                        "candidate_autodb_group": candidate_autodb_group,
                        "current_reason": current_reason,
                        "blocker_type": blocker_type,
                        "proposed_decision": proposed_decision,
                        "proposed_rule": proposed_rule,
                        "count": count,
                    }
                )

        self.stdout.write("audit_autodb_needs_review_compatibility summary:")
        self.stdout.write(f"- rows_needs_review: {len(rows_out)}")
        for key, value in proposed_counter.most_common():
            self.stdout.write(f"- {key}: {value}")
        self.stdout.write(f"- export_csv: {export_csv}")
        self.stdout.write(f"- summary_csv: {summary_csv}")
        self.stdout.write("- writes=0")
        self.stdout.write("- UTR calls=0")


def _contains_manual_review_tokens(raw_category: str) -> bool:
    normalized = _norm(raw_category)
    return any(token in normalized for token in _MANUAL_REVIEW_RAW_CATEGORY_TOKENS)
