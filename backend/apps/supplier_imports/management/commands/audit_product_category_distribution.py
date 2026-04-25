from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.catalog.models import Category, Product
from apps.supplier_imports.models import SupplierRawOffer

TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯіІїЇєЄґҐ0-9]+")
STOPWORDS = {
    "и",
    "й",
    "та",
    "для",
    "на",
    "по",
    "с",
    "з",
    "the",
    "and",
    "for",
    "with",
    "авто",
    "car",
    "auto",
    "system",
    "система",
    "детали",
    "деталь",
    "parts",
    "part",
    "комплект",
    "set",
    "kit",
    "ін",
    "в",
    "из",
    "від",
    "от",
    "до",
    "без",
}

AUTO_ACCESSORY_ROOT_MARKERS = (
    "автохимия и аксессуары",
    "автохімія та аксесуари",
)

TRANSMISSION_PATH_MARKERS = (
    "трансмиссия/кпп",
    "трансмісія / кпп",
)

TRANSMISSION_NAME_MARKERS = (
    "акпп",
    "кпп",
    "автоматичної коробки",
    "автоматической коробки",
)

OIL_FILTER_GASKET_PATH_MARKERS = (
    "прокладка корпуса масляного фильтра",
    "прокладка корпусу масляного фільтра",
)

WASHER_SYSTEM_PATH_MARKERS = (
    "система стеклоочистителя",
    "система склоочисника",
    "система склоочищувача",
)

COOLING_PATH_MARKERS = (
    "охлаждение",
    "охолодження",
)

WEAK_CROSS_ROOT_OVERLAP_TOKENS = {
    "система",
    "системи",
    "системы",
    "гальмівна",
    "гальмівної",
    "гальмівний",
    "тормозная",
    "тормозной",
    "тормозного",
    "масляного",
    "масляний",
    "масляный",
    "механізм",
    "механізму",
    "механизм",
    "механизма",
    "фильтр",
    "фильтра",
    "фільтр",
    "фільтра",
    "насос",
    "насоса",
    "pump",
    "радіатор",
    "радіатора",
    "радиатор",
    "радиатора",
    "ремкомплект",
    "кондиціонер",
    "кондиціонера",
    "conditioner",
    "glass",
    "stop",
}


@dataclass(frozen=True)
class CandidateMove:
    product_id: str
    sku: str
    article: str
    name: str
    assigned_category_id: str
    assigned_category_path: str
    predicted_category_id: str
    predicted_category_path: str
    assigned_score: float
    predicted_score: float
    delta: float
    root_changed: bool
    pred_overlap_tokens: tuple[str, ...]
    pred_specific_tokens: tuple[str, ...]
    assigned_overlap_tokens: tuple[str, ...]


class Command(BaseCommand):
    help = (
        "Audit product category distribution and propose top remap rules "
        "with dry-run impact per rule."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--top",
            type=int,
            default=20,
            help="How many top category-pair remap rules to output.",
        )
        parser.add_argument(
            "--min-predicted-score",
            type=float,
            default=4.0,
            help="Minimum predicted score for a candidate move.",
        )
        parser.add_argument(
            "--min-delta",
            type=float,
            default=3.0,
            help="Minimum score delta (predicted - assigned).",
        )
        parser.add_argument(
            "--min-overlap",
            type=int,
            default=2,
            help="Minimum number of overlapping tokens with predicted category path.",
        )
        parser.add_argument(
            "--min-specific-overlap",
            type=int,
            default=2,
            help="Minimum number of specific overlap tokens (low category document frequency).",
        )
        parser.add_argument(
            "--specific-token-max-df",
            type=int,
            default=18,
            help="Token appears in at most this many categories to be considered specific.",
        )
        parser.add_argument(
            "--include-same-root",
            action="store_true",
            help="Include moves inside the same root category. Default: only root-changed moves.",
        )
        parser.add_argument(
            "--output-json",
            default="/tmp/svom_category_remap_audit.json",
            help="Where to write JSON audit report.",
        )
        parser.add_argument(
            "--output-csv",
            default="/tmp/svom_category_remap_candidates.csv",
            help="Where to write detailed candidate moves CSV.",
        )
        parser.add_argument(
            "--sample-size",
            type=int,
            default=8,
            help="How many sample products to include for each proposed rule in JSON.",
        )

    def handle(self, *args, **options):
        top = max(1, int(options["top"]))
        min_predicted_score = float(options["min_predicted_score"])
        min_delta = float(options["min_delta"])
        min_overlap = max(1, int(options["min_overlap"]))
        min_specific_overlap = max(1, int(options["min_specific_overlap"]))
        specific_token_max_df = max(1, int(options["specific_token_max_df"]))
        include_same_root = bool(options["include_same_root"])
        sample_size = max(1, int(options["sample_size"]))
        output_json = Path(str(options["output_json"])).expanduser().resolve()
        output_csv = Path(str(options["output_csv"])).expanduser().resolve()

        self.stdout.write("Building category token index...")
        category_meta = self._build_category_meta()
        token_to_categories = self._build_token_to_categories(category_meta["category_tokens"])
        token_weight = self._build_token_weight(
            token_to_categories=token_to_categories,
            total_categories=max(len(category_meta["category_tokens"]), 1),
        )

        self.stdout.write("Scoring products against category paths...")
        candidates = self._collect_candidates(
            category_meta=category_meta,
            token_to_categories=token_to_categories,
            token_weight=token_weight,
            min_predicted_score=min_predicted_score,
            min_delta=min_delta,
            min_overlap=min_overlap,
            min_specific_overlap=min_specific_overlap,
            specific_token_max_df=specific_token_max_df,
        )

        if not include_same_root:
            candidates = [row for row in candidates if row.root_changed]

        self.stdout.write(f"Candidate moves after filtering: {len(candidates)}")

        rules = self._build_top_rules(
            candidates=candidates,
            top=top,
            sample_size=sample_size,
        )

        self.stdout.write("Calculating dry-run impact for each proposed rule...")
        for rule in rules:
            product_ids = rule["product_ids"]
            source_category_id = rule["from_category_id"]
            raw_offer_count = SupplierRawOffer.objects.filter(
                matched_product_id__in=product_ids,
                mapped_category_id=source_category_id,
            ).count()
            rule["dry_run"] = {
                "products_would_move": len(product_ids),
                "raw_offers_would_need_remap": int(raw_offer_count),
            }

        self._write_candidates_csv(candidates=candidates, output_csv=output_csv)
        report = {
            "filters": {
                "top": top,
                "min_predicted_score": min_predicted_score,
                "min_delta": min_delta,
                "min_overlap": min_overlap,
                "min_specific_overlap": min_specific_overlap,
                "specific_token_max_df": specific_token_max_df,
                "include_same_root": include_same_root,
            },
            "totals": {
                "products": Product.objects.count(),
                "categories": Category.objects.count(),
                "candidate_moves": len(candidates),
            },
            "proposed_rules": rules,
            "files": {
                "json": str(output_json),
                "csv": str(output_csv),
            },
        }

        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS("Audit report generated."))
        self.stdout.write(f"JSON: {output_json}")
        self.stdout.write(f"CSV: {output_csv}")
        self.stdout.write(f"Top rules: {len(rules)}")
        for index, rule in enumerate(rules, start=1):
            self.stdout.write(
                f"{index}. {rule['from_category_path']} => {rule['to_category_path']} | "
                f"products={rule['dry_run']['products_would_move']} | "
                f"raw_offers={rule['dry_run']['raw_offers_would_need_remap']}"
            )

    @staticmethod
    def _normalize_token(token: str) -> str:
        return token.strip().lower().replace("ё", "е")

    @classmethod
    def _tokenize(cls, text: str) -> set[str]:
        result: set[str] = set()
        for raw in TOKEN_RE.findall(text or ""):
            token = cls._normalize_token(raw)
            if len(token) < 3 or token in STOPWORDS:
                continue
            result.add(token)
        return result

    def _build_category_meta(self) -> dict[str, dict]:
        raw_categories = list(
            Category.objects.values(
                "id",
                "slug",
                "name",
                "name_ru",
                "name_uk",
                "name_en",
                "parent_id",
            )
        )
        by_category_id: dict[str, dict] = {
            str(row["id"]): {
                **row,
                "id": str(row["id"]),
                "parent_id": str(row["parent_id"]) if row["parent_id"] else None,
            }
            for row in raw_categories
        }

        def category_path(category_id: str) -> list[dict]:
            path_nodes: list[dict] = []
            current = by_category_id.get(category_id)
            guard = 0
            while current and guard < 30:
                path_nodes.append(current)
                parent_id = current["parent_id"]
                current = by_category_id.get(parent_id) if parent_id else None
                guard += 1
            path_nodes.reverse()
            return path_nodes

        category_tokens: dict[str, set[str]] = {}
        category_path_title: dict[str, str] = {}
        category_root_id: dict[str, str] = {}

        for category_id in by_category_id:
            path_nodes = category_path(category_id)
            if not path_nodes:
                continue

            text_parts: list[str] = []
            for node in path_nodes:
                text_parts.extend(
                    [
                        node.get("slug") or "",
                        node.get("name") or "",
                        node.get("name_ru") or "",
                        node.get("name_uk") or "",
                        node.get("name_en") or "",
                    ]
                )

            category_tokens[category_id] = self._tokenize(" ".join(text_parts))
            category_path_title[category_id] = " > ".join(
                (node.get("name_ru") or node.get("name_uk") or node.get("name") or node.get("slug") or "")
                for node in path_nodes
            )
            category_root_id[category_id] = path_nodes[0]["id"]

        return {
            "category_tokens": category_tokens,
            "category_path_title": category_path_title,
            "category_root_id": category_root_id,
        }

    @staticmethod
    def _build_token_to_categories(category_tokens: dict[str, set[str]]) -> dict[str, set[str]]:
        token_to_categories: dict[str, set[str]] = defaultdict(set)
        for category_id, tokens in category_tokens.items():
            for token in tokens:
                token_to_categories[token].add(category_id)
        return token_to_categories

    @staticmethod
    def _build_token_weight(*, token_to_categories: dict[str, set[str]], total_categories: int) -> dict[str, float]:
        return {
            token: 1.0 + math.log((1 + total_categories) / (1 + len(category_ids)))
            for token, category_ids in token_to_categories.items()
        }

    def _collect_candidates(
        self,
        *,
        category_meta: dict[str, dict],
        token_to_categories: dict[str, set[str]],
        token_weight: dict[str, float],
        min_predicted_score: float,
        min_delta: float,
        min_overlap: int,
        min_specific_overlap: int,
        specific_token_max_df: int,
    ) -> list[CandidateMove]:
        category_tokens: dict[str, set[str]] = category_meta["category_tokens"]
        category_path_title: dict[str, str] = category_meta["category_path_title"]
        category_root_id: dict[str, str] = category_meta["category_root_id"]

        candidates: list[CandidateMove] = []

        products = Product.objects.values("id", "sku", "article", "name", "category_id")
        for product in products.iterator(chunk_size=5000):
            assigned_category_id = str(product["category_id"])
            product_tokens = self._tokenize(f"{product.get('name') or ''} {product.get('article') or ''}")
            if not product_tokens:
                continue

            candidate_categories: set[str] = set()
            for token in product_tokens:
                candidate_categories.update(token_to_categories.get(token, set()))
            if not candidate_categories:
                continue

            scores: dict[str, float] = defaultdict(float)
            for token in product_tokens:
                categories_for_token = token_to_categories.get(token)
                if not categories_for_token:
                    continue
                weight = token_weight.get(token, 1.0)
                for category_id in categories_for_token:
                    scores[category_id] += weight

            if not scores:
                continue

            predicted_category_id, predicted_score = max(scores.items(), key=lambda pair: pair[1])
            assigned_score = scores.get(assigned_category_id, 0.0)
            if predicted_category_id == assigned_category_id:
                continue

            delta = predicted_score - assigned_score
            if predicted_score < min_predicted_score or delta < min_delta:
                continue

            overlap_predicted = product_tokens & category_tokens.get(predicted_category_id, set())
            overlap_assigned = product_tokens & category_tokens.get(assigned_category_id, set())
            specific_overlap = tuple(
                sorted(
                    token
                    for token in overlap_predicted
                    if len(token_to_categories.get(token, set())) <= specific_token_max_df
                )
            )

            if len(overlap_predicted) < min_overlap or len(specific_overlap) < min_specific_overlap:
                continue

            root_changed = (
                category_root_id.get(assigned_category_id) != category_root_id.get(predicted_category_id)
            )
            assigned_category_path = category_path_title.get(assigned_category_id, "")
            predicted_category_path = category_path_title.get(predicted_category_id, "")
            product_name = product.get("name") or ""

            if root_changed and not self._has_substantive_cross_root_overlap(specific_overlap):
                continue

            if self._is_suppressed_false_positive(
                product_name=product_name,
                assigned_category_path=assigned_category_path,
                predicted_category_path=predicted_category_path,
                root_changed=root_changed,
            ):
                continue

            candidates.append(
                CandidateMove(
                    product_id=str(product["id"]),
                    sku=product.get("sku") or "",
                    article=product.get("article") or "",
                    name=product_name,
                    assigned_category_id=assigned_category_id,
                    assigned_category_path=assigned_category_path,
                    predicted_category_id=predicted_category_id,
                    predicted_category_path=predicted_category_path,
                    assigned_score=round(assigned_score, 3),
                    predicted_score=round(predicted_score, 3),
                    delta=round(delta, 3),
                    root_changed=root_changed,
                    pred_overlap_tokens=tuple(sorted(overlap_predicted)),
                    pred_specific_tokens=specific_overlap,
                    assigned_overlap_tokens=tuple(sorted(overlap_assigned)),
                )
            )

        candidates.sort(key=lambda row: (row.delta, row.predicted_score), reverse=True)
        return candidates

    @staticmethod
    def _has_substantive_cross_root_overlap(specific_overlap: tuple[str, ...]) -> bool:
        return any(token not in WEAK_CROSS_ROOT_OVERLAP_TOKENS for token in specific_overlap)

    @classmethod
    def _is_suppressed_false_positive(
        cls,
        *,
        product_name: str,
        assigned_category_path: str,
        predicted_category_path: str,
        root_changed: bool,
    ) -> bool:
        """Drop known lexical traps where shared words do not imply a category error."""
        assigned_path = cls._normalize_text(assigned_category_path)
        predicted_path = cls._normalize_text(predicted_category_path)
        name = cls._normalize_text(product_name)

        if root_changed and cls._contains_any(assigned_path, AUTO_ACCESSORY_ROOT_MARKERS):
            return True

        if (
            cls._contains_any(assigned_path, TRANSMISSION_PATH_MARKERS)
            and cls._contains_any(name, TRANSMISSION_NAME_MARKERS)
            and cls._contains_any(predicted_path, OIL_FILTER_GASKET_PATH_MARKERS)
        ):
            return True

        if (
            cls._contains_any(assigned_path, WASHER_SYSTEM_PATH_MARKERS)
            and cls._contains_any(predicted_path, COOLING_PATH_MARKERS)
            and cls._contains_any(name, ("омива", "омыва", "склоомива", "стеклоомыва"))
        ):
            return True

        if (
            cls._contains_any(assigned_path, ("водяной насос", "водяний насос"))
            and cls._contains_any(predicted_path, ("датчик температуры", "датчик температури"))
            and cls._contains_any(name, ("насос", "помпа"))
        ):
            return True

        if (
            cls._contains_any(assigned_path, ("воздушный клапан", "повітряний клапан"))
            and cls._contains_any(predicted_path, COOLING_PATH_MARKERS)
            and cls._contains_any(name, ("вторинного повітря", "вторичного воздуха"))
        ):
            return True

        if (
            cls._contains_any(assigned_path, ("регулятор тормозных сил", "регулятор гальмівних сил"))
            and cls._contains_any(predicted_path, ("регулятор тиску палива", "регулятор давления топлива"))
            and cls._contains_any(name, ("гальм", "тормоз"))
        ):
            return True

        return False

    @classmethod
    def _normalize_text(cls, value: str) -> str:
        return cls._normalize_token(value or "")

    @staticmethod
    def _contains_any(value: str, markers: tuple[str, ...]) -> bool:
        return any(marker in value for marker in markers)

    @staticmethod
    def _build_top_rules(
        *,
        candidates: list[CandidateMove],
        top: int,
        sample_size: int,
    ) -> list[dict]:
        buckets: dict[tuple[str, str], list[CandidateMove]] = defaultdict(list)
        for row in candidates:
            buckets[(row.assigned_category_id, row.predicted_category_id)].append(row)

        ranked_pairs = sorted(
            buckets.items(),
            key=lambda item: (len(item[1]), max((row.delta for row in item[1]), default=0.0)),
            reverse=True,
        )

        top_rules: list[dict] = []
        for (source_category_id, target_category_id), rows in ranked_pairs[:top]:
            unique_product_ids = sorted({row.product_id for row in rows})
            average_delta = round(sum(row.delta for row in rows) / max(len(rows), 1), 3)
            top_rules.append(
                {
                    "from_category_id": source_category_id,
                    "from_category_path": rows[0].assigned_category_path if rows else "",
                    "to_category_id": target_category_id,
                    "to_category_path": rows[0].predicted_category_path if rows else "",
                    "candidate_rows": len(rows),
                    "average_delta": average_delta,
                    "product_ids": unique_product_ids,
                    "sample_products": [
                        {
                            "product_id": row.product_id,
                            "sku": row.sku,
                            "name": row.name,
                            "delta": row.delta,
                            "pred_specific_tokens": list(row.pred_specific_tokens),
                        }
                        for row in rows[:sample_size]
                    ],
                }
            )
        return top_rules

    @staticmethod
    def _write_candidates_csv(*, candidates: list[CandidateMove], output_csv: Path) -> None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", encoding="utf-8", newline="") as file_obj:
            fieldnames = [
                "product_id",
                "sku",
                "article",
                "name",
                "assigned_category_id",
                "assigned_category_path",
                "predicted_category_id",
                "predicted_category_path",
                "assigned_score",
                "predicted_score",
                "delta",
                "root_changed",
                "pred_overlap_tokens",
                "pred_specific_tokens",
                "assigned_overlap_tokens",
            ]
            writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
            writer.writeheader()
            for row in candidates:
                writer.writerow(
                    {
                        "product_id": row.product_id,
                        "sku": row.sku,
                        "article": row.article,
                        "name": row.name,
                        "assigned_category_id": row.assigned_category_id,
                        "assigned_category_path": row.assigned_category_path,
                        "predicted_category_id": row.predicted_category_id,
                        "predicted_category_path": row.predicted_category_path,
                        "assigned_score": row.assigned_score,
                        "predicted_score": row.predicted_score,
                        "delta": row.delta,
                        "root_changed": row.root_changed,
                        "pred_overlap_tokens": " ".join(row.pred_overlap_tokens),
                        "pred_specific_tokens": " ".join(row.pred_specific_tokens),
                        "assigned_overlap_tokens": " ".join(row.assigned_overlap_tokens),
                    }
                )
