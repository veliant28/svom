from django.test import SimpleTestCase

from apps.supplier_imports.management.commands.audit_product_category_distribution import Command


class CategoryDistributionAuditSuppressorTests(SimpleTestCase):
    def test_suppresses_auto_chemistry_cross_root_lexical_traps(self):
        self.assertTrue(
            Command._is_suppressed_false_positive(
                product_name='Очисник гальмівної системи "Brake cleaner" Motip 500мл',
                assigned_category_path=(
                    "Автохимия и аксессуары > Автохимия > Очисники та знежирювачі"
                ),
                predicted_category_path=(
                    "Тормозная система > Тормозные элементы > "
                    "Ремкомплект гальмівної системи"
                ),
                root_changed=True,
            )
        )

    def test_suppresses_transmission_filter_to_engine_oil_gasket_trap(self):
        self.assertTrue(
            Command._is_suppressed_false_positive(
                product_name="Ремонтний комплект масляного фільтра АКПП",
                assigned_category_path=(
                    "Сцепление и трансмиссия > Трансмиссия/КПП > Масляный фильтр АКПП"
                ),
                predicted_category_path=(
                    "Двигатель и Система выхлопа > Прокладки > "
                    "Прокладка корпуса масляного фильтра"
                ),
                root_changed=True,
            )
        )

    def test_keeps_non_suppressed_hard_part_candidate(self):
        self.assertFalse(
            Command._is_suppressed_false_positive(
                product_name="Ущільнююче кільце",
                assigned_category_path="Двигатель и Система выхлопа > Прокладки > Прокладка ГБЦ",
                predicted_category_path=(
                    "Двигатель и Система выхлопа > Прокладки > Кольцо уплотнительное"
                ),
                root_changed=False,
            )
        )

    def test_cross_root_overlap_requires_substantive_token(self):
        self.assertFalse(Command._has_substantive_cross_root_overlap(("гальмівної", "системи")))
        self.assertFalse(Command._has_substantive_cross_root_overlap(("механізму", "ремкомплект")))
        self.assertTrue(Command._has_substantive_cross_root_overlap(("гідропідсилювача", "насоса")))
        self.assertTrue(Command._has_substantive_cross_root_overlap(("механізму", "рульового")))
