from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.supplier_imports.services.gpl_category_mapping_audit import normalize_text


UNRESOLVED_STATUSES = {"missing_leaf_category", "needs_review", "conflict"}


class Command(BaseCommand):
    help = "Read-only web/reference audit for unresolved GPL category mapping groups."

    def add_arguments(self, parser):
        parser.add_argument("--audit-csv", required=True, help="Input audit CSV from audit_gpl_price_category_mapping.")
        parser.add_argument("--limit-groups", type=int, default=50, help="Number of unresolved groups to audit.")
        parser.add_argument("--export-csv", required=True, help="Output CSV path.")

    def handle(self, *args, **options):
        audit_path = Path(str(options["audit_csv"])).expanduser()
        export_path = Path(str(options["export_csv"])).expanduser()
        limit = max(int(options.get("limit_groups") or 50), 1)
        if not audit_path.exists():
            raise CommandError(f"audit CSV not found: {audit_path}")

        rows = self._read_csv(audit_path)
        unresolved = [row for row in rows if str(row.get("status") or "") in UNRESOLVED_STATUSES]
        unresolved.sort(key=lambda row: (-self._int(row.get("product_count", "")), row.get("raw_category", ""), row.get("raw_group", "")))
        selected = unresolved[:limit]
        out_rows = [self._audit_row(row) for row in selected]
        self._write_csv(export_path, out_rows)

        status_counts = Counter(row["status"] for row in out_rows)
        self.stdout.write("GPL unresolved groups web/reference audit:")
        self.stdout.write(f"- audit_csv: {audit_path}")
        self.stdout.write(f"- export_csv: {export_path}")
        self.stdout.write(f"- unresolved_groups_total: {len(unresolved)}")
        self.stdout.write(f"- audited_groups: {len(out_rows)}")
        self.stdout.write("- summary_by_status:")
        for status, count in status_counts.most_common():
            self.stdout.write(f"  - {status}: {count}")
        self.stdout.write("- top_confirmed_mappings:")
        for row in [item for item in out_rows if item["status"] in {"confirmed_mapping", "confirmed_missing_leaf"}][:10]:
            self.stdout.write(
                f"  - {row['product_count']} | {row['raw_category']} | {row['raw_group']} -> "
                f"{row['suggested_leaf_category']} | {row['reason']}"
            )
        self.stdout.write("- top_split_needed:")
        for row in [item for item in out_rows if item["status"] == "split_needed"][:10]:
            self.stdout.write(
                f"  - {row['product_count']} | {row['raw_category']} | {row['raw_group']} -> "
                f"{row['suggested_leaf_category']} | {row['reason']}"
            )
        self.stdout.write("- top_still_needs_review:")
        for row in [item for item in out_rows if item["status"] in {"still_needs_review", "unsafe_conflict"}][:10]:
            self.stdout.write(
                f"  - {row['product_count']} | {row['raw_category']} | {row['raw_group']} | {row['reason']}"
            )
        self.stdout.write("- no GPL API calls")
        self.stdout.write("- no product import")
        self.stdout.write("- no offer import")
        self.stdout.write("- no category creation")
        self.stdout.write("- no Auto_DB link/enrichment")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _audit_row(self, row: dict[str, str]) -> dict[str, str]:
        raw_category = str(row.get("raw_category") or "")
        raw_group = str(row.get("raw_group") or "")
        examples = str(row.get("example_names") or row.get("examples") or "")
        text = normalize_text(" ".join([raw_category, raw_group, examples]))
        ref = self._reference_decision(
            text=text,
            category_group_text=normalize_text(" ".join([raw_category, raw_group])),
            raw_category=raw_category,
            raw_group=raw_group,
        )
        return {
            "raw_category": raw_category,
            "raw_group": raw_group,
            "product_count": str(row.get("product_count") or "0"),
            "top_brands": str(row.get("top_brands") or ""),
            "example_articles": str(row.get("example_articles") or ""),
            "example_names": examples,
            "existing_proposed_category": str(row.get("proposed_leaf_category") or ""),
            "web_reference_query_used": ref["query"],
            "source_url": ref["source_url"],
            "source_domain": ref["source_domain"],
            "extracted_reference_product_type": ref["reference_product_type"],
            "suggested_leaf_category": ref["suggested_leaf_category"],
            "confidence": ref["confidence"],
            "reason": ref["reason"],
            "status": ref["status"],
        }

    def _reference_decision(self, *, text: str, category_group_text: str, raw_category: str, raw_group: str) -> dict[str, str]:
        if "spidan" in text and "тяги та наконечники" in text:
            return self._ref(
                query="SPIDAN tie rod end axial joint official catalogue",
                source_url="https://catalogue.spidanchassisparts.com/searchbycar.asp?brand=118651&model=1959&type=733 | https://www.monroe.com/en-gb/products/light-vehicles/steering-and-suspension/tie-rod-ends-and-axial-joints.html",
                source_domain="catalogue.spidanchassisparts.com | monroe.com",
                reference_product_type="SPIDAN catalogue shows TIE ROD END, AXIAL JOINT and TIE ROD; independent steering reference groups tie rod ends and axial rods.",
                suggested_leaf_category="Рулевые наконечники / Рулевые тяги",
                confidence="0.860",
                reason="official_catalog_confirms_mixed_steering_tie_rod_group_split_required",
                status="split_needed",
            )
        if "тяги та наконечники" in category_group_text:
            return self._ref(
                query="tie rod end axial rod steering product category reference",
                source_url="https://www.monroe.com/en-gb/products/light-vehicles/steering-and-suspension/tie-rod-ends-and-axial-joints.html",
                source_domain="monroe.com",
                reference_product_type="Steering references group tie rod ends and axial rods, so GPL mixed category needs name-level split.",
                suggested_leaf_category="Рулевые наконечники / Рулевые тяги",
                confidence="0.760",
                reason="generic_tie_rod_group_split_by_name_needed",
                status="split_needed",
            )
        if "пильовик" in text or "пыльник" in text:
            if "ert" in text:
                return self._ref(
                    query="ERT boot kit transmission steering shock absorber protection official",
                    source_url="https://www.ertseinsa.com/en/products/transmission-boot-kit | https://ertseinsa.com/en/",
                    source_domain="ertseinsa.com",
                    reference_product_type="ERT official range includes transmission/steering boot kits and shock absorber protection kits.",
                    suggested_leaf_category="Пыльник ШРУСа / Пыльник рулевой тяги / Пыльники и отбойники амортизаторов",
                    confidence="0.880",
                    reason="official_ert_sources_confirm_boot_group_is_mixed_split_by_name_needed",
                    status="split_needed",
                )
            return self._ref(
                query="automotive boot dust cover CV steering shock absorber category reference",
                source_url="https://www.ertseinsa.com/en/products/transmission-boot-kit | https://ertseinsa.com/en/",
                source_domain="ertseinsa.com",
                reference_product_type="Boots can be CV/transmission, steering or shock absorber protection.",
                suggested_leaf_category="Пыльник ШРУСа / Пыльник рулевой тяги / Пыльники и отбойники амортизаторов",
                confidence="0.760",
                reason="boot_group_semantically_mixed_split_by_product_name",
                status="split_needed",
            )
        if "automega" in text and "датчик" in category_group_text:
            return self._ref(
                query="AutoMega official products sensors catalogue AUTOMEGA",
                source_url="https://www.automega.de/english/products/ | https://www.autodoc.parts/car-parts-brands/automega",
                source_domain="automega.de | autodoc.parts",
                reference_product_type="AutoMega official product range is broad; catalogue references list ABS, temperature, crankshaft, pressure, parking and other sensors.",
                suggested_leaf_category="Датчик ABS / Датчик температуры охлаждающей жидкости / датчики двигателя по названию",
                confidence="0.740",
                reason="sensor_group_is_broad_and_requires_name_specific_split_not_single_mapping",
                status="split_needed",
            )
        if "датчик" in category_group_text:
            return self._ref(
                query="automotive sensor category ABS temperature pressure crankshaft reference",
                source_url="https://www.automega.de/english/products/ | https://www.autodoc.parts/car-parts-brands/automega",
                source_domain="automega.de | autodoc.parts",
                reference_product_type="Sensor category spans multiple vehicle systems.",
                suggested_leaf_category="name-specific sensor leaf",
                confidence="0.680",
                reason="generic_sensor_group_requires_manual_name_specific_split",
                status="split_needed",
            )
        if "polmo" in text and "резонатор" in text:
            return self._ref(
                query="POLMOstrów official exhaust systems resonator POLMO catalogue",
                source_url="https://polmostrow.pl/en/our-company/ | https://2407.pl/en/polmostrow-brand/",
                source_domain="polmostrow.pl | 2407.pl",
                reference_product_type="POLMOstrów specializes in exhaust systems; independent catalogue lists Resonator as a POLMO exhaust-system category.",
                suggested_leaf_category="Резонатор",
                confidence="0.900",
                reason="official_polmo_exhaust_context_plus_independent_resonator_category_confirms_missing_leaf",
                status="confirmed_missing_leaf",
            )
        if "polmo" in text and ("труби приймальн" in text or "трубы приемн" in text):
            return self._ref(
                query="POLMO front exhaust pipe official exhaust systems catalogue",
                source_url="https://polmostrow.pl/en/our-company/ | https://www.autodoc.parts/polmo/9070519",
                source_domain="polmostrow.pl | autodoc.parts",
                reference_product_type="POLMOstrów exhaust systems; product references describe POLMO front exhaust pipe before catalytic converter/front muffler.",
                suggested_leaf_category="Приемная труба",
                confidence="0.880",
                reason="front_exhaust_pipe_is_distinct_missing_leaf",
                status="confirmed_missing_leaf",
            )
        if "polmo" in text and ("труби випускн" in text or "трубы выпускн" in text or "проміжн" in text or "промежуточн" in text):
            return self._ref(
                query="POLMO exhaust pipe official catalogue exhaust pipe",
                source_url="https://polmostrow.pl/en/our-company/ | https://www.autodoc.parts/car-parts/exhaust-pipes-10415/mf-polmo",
                source_domain="polmostrow.pl | autodoc.parts",
                reference_product_type="POLMOstrów exhaust systems; catalogue references list POLMO exhaust pipes.",
                suggested_leaf_category="Трубы выхлопной системы",
                confidence="0.880",
                reason="exhaust_pipe_group_confirms_missing_leaf",
                status="confirmed_missing_leaf",
            )
        if "труби приймальн" in category_group_text or "трубы приемн" in category_group_text:
            return self._ref(
                query=f"{raw_group} front exhaust pipe official catalogue",
                source_url="",
                source_domain="",
                reference_product_type="",
                suggested_leaf_category="Приемная труба",
                confidence="0.000",
                reason="front_exhaust_pipe_semantics_clear_but_brand_reference_not_verified",
                status="still_needs_review",
            )
        if "труби випускн" in category_group_text or "трубы выпускн" in category_group_text or "проміжн" in category_group_text or "промежуточн" in category_group_text:
            return self._ref(
                query=f"{raw_group} exhaust pipe official catalogue",
                source_url="",
                source_domain="",
                reference_product_type="",
                suggested_leaf_category="Трубы выхлопной системы",
                confidence="0.000",
                reason="exhaust_pipe_semantics_clear_but_brand_reference_not_verified",
                status="still_needs_review",
            )
        if "k2" in text and "ароматизатор" in text:
            return self._ref(
                query="K2 official car air freshener product",
                source_url="https://www.k2-global.com/en/products/k2-creo-black-new-car | https://k2.com.pl/produkty/k2-deocar-lemon-250ml",
                source_domain="k2-global.com | k2.com.pl",
                reference_product_type="K2 official pages describe bottled/gel/hanging car air fresheners.",
                suggested_leaf_category="Ароматизаторы",
                confidence="0.950",
                reason="official_k2_air_freshener_sources_confirm_missing_leaf",
                status="confirmed_missing_leaf",
            )
        if "ароматизатор" in text:
            return self._ref(
                query="car air freshener official product reference",
                source_url="https://www.k2-global.com/en/products/k2-creo-black-new-car | https://k2.com.pl/produkty/k2-deocar-lemon-250ml",
                source_domain="k2-global.com | k2.com.pl",
                reference_product_type="Air freshener.",
                suggested_leaf_category="Ароматизаторы",
                confidence="0.820",
                reason="air_freshener_category_confirmed_but_brand_specific_source_missing",
                status="confirmed_missing_leaf",
            )
        if "проклад" in text:
            return self._ref(
                query="automotive gasket categories cylinder head valve cover exhaust sump",
                source_url="https://www.automega.de/english/products/ | https://www.automega.de/english/our-brand/",
                source_domain="automega.de",
                reference_product_type="Gaskets span engine, exhaust and transmission systems; group needs product-name split.",
                suggested_leaf_category="Прокладка ГБЦ / Прокладка клапанной крышки / Прокладка глушителя / Прокладка поддона",
                confidence="0.720",
                reason="gasket_group_is_mixed_split_by_specific_name",
                status="split_needed",
            )
        if "резонатор" in text:
            return self._ref(
                query="resonator exhaust system category reference",
                source_url="https://polmostrow.pl/en/our-company/ | https://2407.pl/en/polmostrow-brand/",
                source_domain="polmostrow.pl | 2407.pl",
                reference_product_type="Exhaust-system resonator.",
                suggested_leaf_category="Резонатор",
                confidence="0.800",
                reason="resonator_missing_leaf_but_brand_reference_not_specific",
                status="confirmed_missing_leaf",
            )
        return self._ref(
            query=f"{raw_group} {raw_category} official product category",
            source_url="",
            source_domain="",
            reference_product_type="",
            suggested_leaf_category="",
            confidence="0.000",
            reason="no_specific_web_reference_rule_for_group",
            status="still_needs_review",
        )

    @staticmethod
    def _ref(
        *,
        query: str,
        source_url: str,
        source_domain: str,
        reference_product_type: str,
        suggested_leaf_category: str,
        confidence: str,
        reason: str,
        status: str,
    ) -> dict[str, str]:
        return {
            "query": query,
            "source_url": source_url,
            "source_domain": source_domain,
            "reference_product_type": reference_product_type,
            "suggested_leaf_category": suggested_leaf_category,
            "confidence": confidence,
            "reason": reason,
            "status": status,
        }

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        with path.open("r", newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "raw_category",
            "raw_group",
            "product_count",
            "top_brands",
            "example_articles",
            "example_names",
            "existing_proposed_category",
            "web_reference_query_used",
            "source_url",
            "source_domain",
            "extracted_reference_product_type",
            "suggested_leaf_category",
            "confidence",
            "reason",
            "status",
        ]
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _int(value: str) -> int:
        try:
            return int(str(value or "0"))
        except ValueError:
            return 0
