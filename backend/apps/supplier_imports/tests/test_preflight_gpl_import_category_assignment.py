from __future__ import annotations

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Category
from apps.supplier_imports.services.gpl_category_mapping_audit import CategoryDecision, CategoryTarget, STATUS_ACTIVE, STATUS_REVIEW
from apps.supplier_imports.services.gpl_import_category_assignment import (
    MAPPING_STATUS_ASSIGNED_GROUP,
    MAPPING_STATUS_ASSIGNED_ROW,
    MAPPING_STATUS_CONFLICT,
    MAPPING_STATUS_NEEDS,
    GplImportCategoryAssignmentResolver,
)


class _FakeAuditor:
    def __init__(self, *, group_decision: CategoryDecision, row_target: CategoryTarget | None) -> None:
        self._group_decision = group_decision
        self._row_target = row_target

    def decide_group(self, *, rows: list[dict[str, str]]) -> CategoryDecision:
        return self._group_decision

    def classify_row(self, *, row: dict[str, str]) -> CategoryTarget | None:
        return self._row_target


class GplImportCategoryAssignmentResolverTests(TestCase):
    def setUp(self):
        self.engine_root = _root("engine-root", "Двигатель и выхлоп")
        self.suspension_root = _root("suspension-root", "Подвеска и рулевое")
        self.care_root = _root("care-root", "Автохимия и аксессуары")

        self.root_target = _root("root-target", "Root Target")
        self.menu_group_target = Category.objects.create(
            parent=self.engine_root,
            name="Меню группа",
            name_uk="Меню группа",
            name_ru="Меню группа",
            name_en="Menu group",
            slug="menu-group",
            is_active=True,
            is_assignable=False,
            source=Category.SOURCE_MANUAL,
        )

        self.amortizatory = _leaf(self.suspension_root, "amortizatory", "Амортизаторы")
        self.rezonator = _leaf(self.engine_root, "rezonator", "Резонатор")
        _leaf(self.engine_root, "glushitel", "Глушитель")
        _leaf(self.care_root, "avtoemali-i-kraski", "Автоэмали и краски")
        _leaf(self.care_root, "sredstva-zashchity-i-spetsodezhda", "Средства защиты и спецодежда")

    def test_assigns_only_assignable_leaf(self):
        resolver = GplImportCategoryAssignmentResolver(
            auditor=_FakeAuditor(
                group_decision=CategoryDecision(
                    status=STATUS_ACTIVE,
                    target_slug="amortizatory",
                    target_name="Амортизаторы",
                    root_name="Подвеска и рулевое",
                    confidence=0.99,
                    reason="group_exact",
                ),
                row_target=None,
            )
        )

        group_decision = resolver.decide_group(rows=[_row(category="Амортизатори", group="FENOX", name="Амортизатор FENOX")])
        row_decision = resolver.decide_row(
            row=_row(category="Амортизатори", group="FENOX", name="Амортизатор FENOX"),
            group_decision=group_decision,
        )

        self.assertEqual(group_decision.mapping_status, MAPPING_STATUS_ASSIGNED_GROUP)
        self.assertEqual(row_decision.mapping_status, MAPPING_STATUS_ASSIGNED_GROUP)
        self.assertTrue(row_decision.category_is_assignable)
        self.assertEqual(row_decision.category_id, str(self.amortizatory.id))

    def test_root_target_rejected(self):
        resolver = GplImportCategoryAssignmentResolver(
            auditor=_FakeAuditor(
                group_decision=CategoryDecision(
                    status=STATUS_ACTIVE,
                    target_slug="root-target",
                    target_name="Root Target",
                    root_name="Root Target",
                    confidence=0.90,
                    reason="bad_root",
                ),
                row_target=None,
            )
        )

        decision = resolver.decide_group(rows=[_row(category="Any", group="Any", name="Any")])
        self.assertEqual(decision.mapping_status, MAPPING_STATUS_CONFLICT)
        self.assertTrue(decision.invalid_target)
        self.assertEqual(decision.reason, "target_root_forbidden")

    def test_menu_group_target_rejected(self):
        resolver = GplImportCategoryAssignmentResolver(
            auditor=_FakeAuditor(
                group_decision=CategoryDecision(
                    status=STATUS_ACTIVE,
                    target_slug="menu-group",
                    target_name="Меню группа",
                    root_name="Двигатель и выхлоп",
                    confidence=0.90,
                    reason="bad_menu",
                ),
                row_target=None,
            )
        )

        decision = resolver.decide_group(rows=[_row(category="Any", group="Any", name="Any")])
        self.assertEqual(decision.mapping_status, MAPPING_STATUS_CONFLICT)
        self.assertTrue(decision.non_assignable_target)
        self.assertEqual(decision.reason, "target_non_assignable_forbidden")

    def test_missing_mapping_returns_needs_category_mapping(self):
        resolver = GplImportCategoryAssignmentResolver(
            auditor=_FakeAuditor(
                group_decision=CategoryDecision(
                    status=STATUS_REVIEW,
                    target_slug="",
                    target_name="",
                    root_name="",
                    confidence=0.0,
                    reason="no_confident_leaf_signal",
                ),
                row_target=None,
            )
        )

        group_decision = resolver.decide_group(rows=[_row(category="Неизвестно", group="BRAND", name="No match")])
        row_decision = resolver.decide_row(
            row=_row(category="Неизвестно", group="BRAND", name="No match"),
            group_decision=group_decision,
        )

        self.assertEqual(row_decision.mapping_status, MAPPING_STATUS_NEEDS)
        self.assertEqual(row_decision.category_id, "")

    def test_row_level_mapping_used_when_group_not_assigned(self):
        resolver = GplImportCategoryAssignmentResolver(
            auditor=_FakeAuditor(
                group_decision=CategoryDecision(
                    status=STATUS_REVIEW,
                    target_slug="",
                    target_name="",
                    root_name="",
                    confidence=0.0,
                    reason="group_needs_review",
                ),
                row_target=CategoryTarget(slug="amortizatory", confidence=0.94, reason="row_rule:shock"),
            )
        )

        group_decision = resolver.decide_group(rows=[_row(category="Категория", group="Brand", name="Амортизатор")])
        row_decision = resolver.decide_row(
            row=_row(category="Категория", group="Brand", name="Амортизатор"),
            group_decision=group_decision,
        )

        self.assertEqual(row_decision.mapping_status, MAPPING_STATUS_ASSIGNED_ROW)
        self.assertEqual(row_decision.proposed_category_slug, "amortizatory")

    def test_precise_row_mapping_overrides_broad_group_mapping(self):
        resolver = GplImportCategoryAssignmentResolver(
            auditor=_FakeAuditor(
                group_decision=CategoryDecision(
                    status=STATUS_ACTIVE,
                    target_slug="amortizatory",
                    target_name="Амортизаторы",
                    root_name="Подвеска и рулевое",
                    confidence=0.94,
                    reason="broad_group",
                ),
                row_target=CategoryTarget(slug="rezonator", confidence=0.95, reason="precise_row"),
            )
        )

        group_decision = resolver.decide_group(rows=[_row(category="Категория", group="Brand", name="Амортизатор")])
        row_decision = resolver.decide_row(
            row=_row(category="Категория", group="Brand", name="Резонатор"),
            group_decision=group_decision,
        )

        self.assertEqual(row_decision.mapping_status, MAPPING_STATUS_ASSIGNED_ROW)
        self.assertEqual(row_decision.proposed_category_slug, "rezonator")
        self.assertEqual(row_decision.reason, "row_rule_overrides_group_mapping")

    def test_glushitel_rezonator_never_maps_to_amortizatory(self):
        resolver = GplImportCategoryAssignmentResolver()
        group_decision = resolver.decide_group(rows=[_row(category="Резонатори", group="POLMO", name="Резонатор POLMO")])
        row_decision = resolver.decide_row(
            row=_row(category="Резонатори", group="POLMO", name="Резонатор POLMO"),
            group_decision=group_decision,
        )

        self.assertNotEqual(row_decision.proposed_category_slug, "amortizatory")

    def test_negative_ppe_signals_do_not_map_to_auto_paint(self):
        resolver = GplImportCategoryAssignmentResolver()
        group_decision = resolver.decide_group(
            rows=[_row(category="Рукавички", group="DOLONI", name="Рукавички захисні абразивні")]
        )
        row_decision = resolver.decide_row(
            row=_row(category="Рукавички", group="DOLONI", name="Рукавички захисні абразивні"),
            group_decision=group_decision,
        )

        self.assertNotEqual(row_decision.proposed_category_slug, "avtoemali-i-kraski")


class GplImportCategoryAssignmentPreflightCommandTests(TestCase):
    def setUp(self):
        engine_root = _root("engine-root-cmd", "Двигатель и выхлоп")
        suspension_root = _root("suspension-root-cmd", "Подвеска и рулевое")
        care_root = _root("care-root-cmd", "Автохимия и аксессуары")

        _leaf(engine_root, "rezonator", "Резонатор")
        _leaf(suspension_root, "amortizatory", "Амортизаторы")
        _leaf(care_root, "sredstva-zashchity-i-spetsodezhda", "Средства защиты и спецодежда")

    def test_preflight_does_not_create_categories_and_does_not_call_utr(self):
        with TemporaryDirectory() as tmp_dir:
            price_csv = Path(tmp_dir) / "gpl.csv"
            full_csv = Path(tmp_dir) / "full.csv"
            unresolved_csv = Path(tmp_dir) / "unresolved.csv"
            summary_csv = Path(tmp_dir) / "summary.csv"
            unresolved_groups_csv = Path(tmp_dir) / "unresolved_groups.csv"

            price_csv.write_text(
                "\n".join(
                    [
                        "Категорія,Група ТД,Артикул ТД,Найменування,Опис",
                        "Резонатори,POLMO,111,Резонатор POLMO,",
                        "Рукавички,DOLONI,222,Рукавички захисні абразивні,",
                        "Невідома категорія,TEST,333,Рідкісний товар,",
                    ]
                ),
                encoding="utf-8",
            )

            before_categories = Category.objects.count()
            out = StringIO()
            with patch(
                "apps.autocatalog.services.utr_article_detail_resolver_service.UtrArticleDetailResolverService.collect_detail_ids"
            ) as utr_mock:
                call_command(
                    "preflight_gpl_import_category_assignment",
                    "--source",
                    "gpl",
                    "--path",
                    str(price_csv),
                    "--export-csv",
                    str(full_csv),
                    "--unresolved-csv",
                    str(unresolved_csv),
                    "--summary-csv",
                    str(summary_csv),
                    "--unresolved-groups-csv",
                    str(unresolved_groups_csv),
                    stdout=out,
                )

            after_categories = Category.objects.count()
            self.assertEqual(before_categories, after_categories)
            self.assertFalse(utr_mock.called)
            self.assertTrue(full_csv.exists())
            self.assertTrue(unresolved_csv.exists())
            self.assertTrue(summary_csv.exists())
            self.assertTrue(unresolved_groups_csv.exists())
            self.assertIn("no product import", out.getvalue())
            self.assertIn("UTR calls=0", out.getvalue())



def _root(slug: str, name: str) -> Category:
    return Category.objects.create(
        name=name,
        name_uk=name,
        name_ru=name,
        name_en=name,
        slug=slug,
        is_active=True,
        is_assignable=False,
        source=Category.SOURCE_MANUAL,
    )



def _leaf(parent: Category, slug: str, name: str) -> Category:
    return Category.objects.create(
        parent=parent,
        name=name,
        name_uk=name,
        name_ru=name,
        name_en=name,
        slug=slug,
        is_active=True,
        is_assignable=True,
        source=Category.SOURCE_MANUAL,
    )



def _row(*, category: str, group: str, name: str) -> dict[str, str]:
    return {
        "Категорія": category,
        "Група ТД": group,
        "Найменування": name,
        "Опис": "",
    }
