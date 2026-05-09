from __future__ import annotations

import csv
from django.test import TestCase
from django.core.management import call_command
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from apps.catalog.models import Category
from apps.supplier_imports.services.gpl_category_mapping_audit import (
    STATUS_ACTIVE,
    STATUS_REVIEW,
    STATUS_MISSING,
    GplCategoryMappingAuditor,
)


class GplCategoryMappingAuditorTests(TestCase):
    def setUp(self):
        self.engine_root = _root("engine", "Двигатель и выхлоп")
        self.suspension_root = _root("suspension", "Подвеска и рулевое")
        self.electric_root = _root("electric", "Электрика и освещение")
        self.brake_root = _root("brake", "Тормозная система")
        self.care_root = _root("care", "Автохимия и аксессуары")
        self.wheels_root = _root("wheels", "Колёса и шины")

        _leaf(self.engine_root, "maslianyi-filtr", "Масляный фильтр")
        _leaf(self.engine_root, "maslianyi-filtr-akpp", "Масляный фильтр АКПП")
        _leaf(self.engine_root, "remen-privodnoi", "Ремень приводной")
        _leaf(self.engine_root, "motornoe-maslo", "Моторное масло")
        _leaf(self.engine_root, "maslo-transmissionnoe", "Масло трансмиссионное")
        _leaf(self.engine_root, "rezonator", "Резонатор")
        _leaf(self.engine_root, "priemnaia-truba", "Приемная труба")
        _leaf(self.engine_root, "truby-vykhlopnoi-sistemy", "Трубы выхлопной системы")
        _leaf(self.suspension_root, "amortizatory", "Амортизаторы")
        _leaf(self.suspension_root, "opora-amortizatora", "Опора амортизатора")
        _leaf(self.suspension_root, "opornyi-podshipnik", "Опорный подшипник")
        _leaf(self.suspension_root, "sharovye-opory", "Шаровые опоры")
        _leaf(self.suspension_root, "rulevye-nakonechniki", "Рулевые наконечники")
        _leaf(self.suspension_root, "rulevye-tiagi", "Рулевые тяги")
        _leaf(self.suspension_root, "pylniki-i-otboiniki-amortizatorov", "Пыльники и отбойники амортизаторов")
        _leaf(self.suspension_root, "pylnik-rulevoi-tiagi", "Пыльник рулевой тяги")
        _leaf(self.electric_root, "svechi-zazhiganiia", "Свечи зажигания")
        _leaf(self.electric_root, "provoda-vysokovoltnye", "Провода высоковольтные")
        _leaf(self.electric_root, "avtolampy", "Автолампы")
        _leaf(self.electric_root, "trapetsiia-stekloochistitelia", "Трапеция стеклоочистителя")
        _leaf(self.electric_root, "povodok-stekloochistitelia", "Поводок стеклоочистителя")
        _leaf(self.electric_root, "forsunki-omyvatelia-stekla", "Форсунки омывателя стекла")
        _leaf(self.electric_root, "podrulevye-perekliuchateli", "Подрулевые переключатели")
        _leaf(self.electric_root, "datchik-abs", "Датчик ABS")
        _leaf(self.electric_root, "datchik-temperatury-okhlazhdaiushchei-zhidkosti", "Датчик температуры охлаждающей жидкости")
        _leaf(self.engine_root, "datchik-davleniia-nadduva-turbiny", "Датчик давления наддува турбины")
        _leaf(self.engine_root, "datchik-davleniia-vyhlopnyh-gazov", "Датчик давления выхлопных газов")
        _leaf(self.engine_root, "prokladka-gbts", "Прокладка ГБЦ")
        _leaf(self.engine_root, "prokladka-klapannoi-kryshki", "Прокладка клапанной крышки")
        _leaf(self.engine_root, "prokladka-glushitelia", "Прокладка глушителя")
        _leaf(self.engine_root, "prokladka-poddona", "Прокладка поддона")
        _leaf(self.engine_root, "komplekt-prokladok-dvigatelia", "Комплект прокладок двигателя")
        _leaf(self.engine_root, "podushki-dvigatelia", "Подушки двигателя")
        _leaf(self.engine_root, "rolik-grm", "Ролик ГРМ")
        _leaf(self.engine_root, "rolik-remnia-privodnogo", "Ролик ремня приводного")
        _leaf(self.engine_root, "vodianoi-nasos", "Водяной насос")
        _leaf(self.engine_root, "toplivnyi-nasos", "Топливный насос")
        _leaf(self.engine_root, "vkladyshi-korennye", "Вкладыши коренные")
        _leaf(self.engine_root, "vkladyshi-shatunnye", "Вкладыши шатунные")
        _leaf(self.brake_root, "tormoznoi-shlang", "Тормозной шланг")
        _leaf(self.brake_root, "glavnyi-tormoznoi-tsilindr", "Главный тормозной цилиндр")
        _leaf(self.brake_root, "rabochii-tormoznoi-tsilindr", "Рабочий тормозной цилиндр")
        _leaf(self.brake_root, "tros-ruchnika", "Трос ручника")
        _leaf(self.brake_root, "trosy-tormoznoi-sistemy", "Тросы тормозной системы")
        _leaf(self.care_root, "uhod-za-avto", "Уход за авто")
        _leaf(self.care_root, "aromatizatory", "Ароматизаторы")
        _leaf(self.care_root, "gubki-i-salfetki-dlia-avto", "Губки и салфетки для авто")
        _leaf(self.care_root, "shchetki-skrebki-i-vodosgony-dlia-avto", "Щетки, скребки и водосгоны для авто")
        _leaf(self.care_root, "antikorroziinye-sredstva-i-pokrytiia", "Антикоррозийные средства и покрытия")
        _leaf(self.care_root, "polirol-kuzova", "Полироли кузова")
        _leaf(self.care_root, "bytovaia-khimiia", "Бытовая химия")
        _leaf(self.care_root, "rastvoriteli-i-obezzhirivateli", "Растворители и обезжириватели")
        _leaf(self.care_root, "sredstva-zashchity-i-spetsodezhda", "Средства защиты и спецодежда")
        _leaf(self.care_root, "homuty-stiazhki-i-zazhimy", "Хомуты, стяжки и зажимы")
        _leaf(self.care_root, "golovki-tortsevye", "Головки торцевые")
        _leaf(self.care_root, "domkraty", "Домкраты")
        _leaf(self.care_root, "gidravlicheskoe-maslo", "Гидравлическое масло")
        _leaf(self.care_root, "prisadki", "Присадки")
        _leaf(self.wheels_root, "zimnie-shiny", "Зимние шины")
        _leaf(self.wheels_root, "letnie-shiny", "Летние шины")
        _leaf(self.wheels_root, "vsesezonnye-shiny", "Всесезонные шины")
        self.body_root = _root("body", "Детали кузова")
        _leaf(self.body_root, "dvorniki", "Дворники")
        self.transmission_root = _root("transmission", "Сцепление и трансмиссия")
        _leaf(self.transmission_root, "shrus", "ШРУС")
        _leaf(self.transmission_root, "pylnik-shrusa", "Пыльник ШРУСа")
        _leaf(self.transmission_root, "remkomplekt-tsilindra-stsepleniia", "Ремкомплект цилиндра сцепления")
        _leaf(self.transmission_root, "trosik-spidometra", "Тросик спидометра")
        _leaf(self.transmission_root, "trosik-gaza", "Тросик газа")
        _leaf(self.transmission_root, "trosik-stsepleniia", "Тросик сцепления")
        _leaf(self.transmission_root, "tros-zamka-dveri", "Трос замка двери")

    def test_maps_ukrainian_oil_filter_plural_to_assignable_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Фільтри оливи", group="WIX FILTERS", name="Фільтр оливи WIX")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "maslianyi-filtr")

    def test_maps_spark_plugs_to_assignable_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Свічки запалювання", group="BRISK", name="Свічка запалювання BRISK")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "svechi-zazhiganiia")

    def test_drive_belt_beats_generator_token(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Ремені", group="OPTIBELT", name="Ремень генератора OPTIBELT")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "remen-privodnoi")

    def test_shock_absorber_beats_hydraulic_text(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Амортизатори", group="FENOX", name="Амортизатор газомасляний гідравлічний")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "amortizatory")

    def test_shock_mount_does_not_map_to_shock_absorbers(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Опори амортизаторів", group="AUTOMEGA", name="Опора амортизатора AUTOMEGA")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "opora-amortizatora")

    def test_shock_support_bearing_does_not_map_to_shock_absorbers(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Опори амортизаторів", group="AUTOMEGA", name="Підшипник опори амортизатора AUTOMEGA")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "opornyi-podshipnik")

    def test_shock_bump_stop_does_not_map_to_shock_absorbers(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Відбійники амортизаторів", group="TEDGUM", name="Відбійник амортизатора TEDGUM")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "pylniki-i-otboiniki-amortizatorov")

    def test_hydraulic_jack_does_not_map_to_hydraulic_oil(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Домкрати", group="LAVITA", name="Домкрат Lavita гідравлічний 10 т")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "domkraty")

    def test_hydraulic_filter_does_not_map_to_hydraulic_oil(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Спеціалізовані фільтри", group="BALDWIN", name="Фільтр гідравлічний BALDWIN")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "maslianyi-filtr")

    def test_atf_filter_does_not_map_to_hydraulic_oil(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Спеціалізовані фільтри", group="WIX FILTERS", name="Фільтр АКПП WIX FILTERS")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "maslianyi-filtr-akpp")

    def test_specialized_filter_fallback_does_not_map_to_hydraulic_oil(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Спеціалізовані фільтри", group="WIX FILTERS", name="Фільтр системи охолодження WIX FILTERS")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "maslianyi-filtr")

    def test_hydraulic_oil_still_maps_to_hydraulic_oil(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Спеціалізовані оливи", group="K2", name="Олива гідравлічна K2 HLP 46 Hydraulic 20 л")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "gidravlicheskoe-maslo")

    def test_transmission_oil_10w30_does_not_map_to_engine_oil(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Трансмісійні оливи", group="MOBIL", name="Олива трансмісійна MOBIL GL-4 10W-30 20 л")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "maslo-transmissionnoe")

    def test_lamp_wattage_does_not_map_to_engine_oil(self):
        target = GplCategoryMappingAuditor().classify_row(
            row=_row(category="Лампи", group="GENERAL ELECTRIC", name="Лампа автомобільна 12V H10W 10W BA9S")
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.slug, "avtolampy")

    def test_brake_cylinder_repair_kit_does_not_map_to_clutch_repair_kit(self):
        target = GplCategoryMappingAuditor().classify_row(
            row=_row(category="Ремкомплекти гальмівної системи", group="ERT", name="Ремкомплект головного гальмівного циліндра ERT")
        )

        self.assertIsNone(target)

    def test_anti_aerosol_respirator_does_not_map_to_aerosol_paint(self):
        target = GplCategoryMappingAuditor().classify_row(
            row=_row(category="Матеріали для підготовки та фарбування", group="YATO", name="Респіратор протиаерозольний YATO з клапаном FFP2")
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.slug, "sredstva-zashchity-i-spetsodezhda")

    def test_wiper_blades_do_not_map_to_car_care(self):
        target = GplCategoryMappingAuditor().classify_row(
            row=_row(category="Щітки склоочисників", group="AT", name="Щітка склоочисника AT 330 мм Classic")
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.slug, "dvorniki")

    def test_wiper_linkage_does_not_map_to_car_care(self):
        target = GplCategoryMappingAuditor().classify_row(
            row=_row(category="Механізми склоочисників", group="AT", name="Трапеція приводу склоочисників АТ Daewoo Lanos")
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.slug, "trapetsiia-stekloochistitelia")

    def test_wiper_switch_does_not_map_to_car_care(self):
        target = GplCategoryMappingAuditor().classify_row(
            row=_row(category="Перемикачі", group="Aurora", name="Перемикач склоочисника Aurora Daewoo Lanos")
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.slug, "podrulevye-perekliuchateli")

    def test_cockpit_polish_does_not_map_to_aerosol_paint(self):
        target = GplCategoryMappingAuditor().classify_row(
            row=_row(category="Поліролі торпедо", group="K2", name="Поліроль для пластику K2 Polo Cockpit Ваніль прозорий аерозоль 600 мл")
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.slug, "uhod-za-avto")

    def test_repeated_unknown_group_becomes_missing_leaf_not_root_mapping(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[
                _row(category="Невідома категорія", group="TEST", name="Невідомий товар 1"),
                _row(category="Невідома категорія", group="TEST", name="Невідомий товар 2"),
                _row(category="Невідома категорія", group="TEST", name="Невідомий товар 3"),
            ]
        )

        self.assertEqual(decision.status, STATUS_MISSING)
        self.assertEqual(decision.target_slug, "")

    def test_polmo_resonators_map_to_resonator_leaf_when_seeded(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Резонатори", group="POLMO", name="Резонатор POLMO")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "rezonator")

    def test_k2_air_fresheners_map_to_aromatizatory_leaf_when_seeded(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Ароматизатори", group="K2", name="Ароматизатор K2 Vento")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "aromatizatory")

    def test_little_trees_air_fresheners_map_to_aromatizatory_leaf_when_seeded(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Ароматизатори", group="LITTLE TREES", name="Ароматизатор елка LITTLE TREES")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "aromatizatory")

    def test_tmk_resonators_map_to_resonator_leaf_when_seeded(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Резонатори", group="ТМК", name="Резонатор ТМК")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "rezonator")

    def test_bosal_resonators_map_to_resonator_leaf_when_seeded(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Резонатори", group="BOSAL", name="Резонатор BOSAL")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "rezonator")

    def test_spidan_tie_group_splits_by_name_to_tie_rod_end(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Тяги та наконечники", group="SPIDAN", name="Наконечник рулевой тяги SPIDAN")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "rulevye-nakonechniki")

    def test_spidan_tie_group_splits_by_name_to_tie_rod(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Тяги та наконечники", group="SPIDAN", name="Рулевая тяга SPIDAN")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "rulevye-tiagi")

    def test_ert_boot_group_splits_to_cv_boot_by_name(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Пильовики", group="ERT", name="Пильник ШРУС ERT")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "pylnik-shrusa")

    def test_ert_boot_group_splits_to_shock_boot_by_name(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Пильовики", group="ERT", name="Пильник амортизатора ERT")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "pylniki-i-otboiniki-amortizatorov")

    def test_ert_boot_group_splits_to_steering_boot_by_name(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Пильовики", group="ERT", name="Пильник рулевой тяги ERT")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "pylnik-rulevoi-tiagi")

    def test_automega_sensors_group_without_specific_signal_stays_review(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Датчики", group="AUTOMEGA", name="Датчик AUTOMEGA универсальный")]
        )

        self.assertEqual(decision.status, STATUS_REVIEW)
        self.assertEqual(decision.target_slug, "")

    def test_automega_sensors_group_maps_abs_by_name(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Датчики", group="AUTOMEGA", name="Датчик ABS AUTOMEGA")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "datchik-abs")

    def test_prokladki_group_without_specific_signal_stays_review(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Прокладки", group="AT", name="Прокладка AT универсальная")]
        )

        self.assertEqual(decision.status, STATUS_REVIEW)
        self.assertEqual(decision.target_slug, "")

    def test_prokladki_group_maps_gbts_by_name(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Прокладки", group="AT", name="Прокладка ГБЦ AT")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "prokladka-gbts")

    def test_engine_mount_group_maps_to_engine_mount_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Подушки та опори двигуна", group="TEDGUM", name="Опора двигуна TEDGUM")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "podushki-dvigatelia")

    def test_brake_cylinders_group_maps_master_cylinder_by_name(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Циліндри гальмівної системи", group="FENOX", name="Циліндр гальмівний головний FENOX")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "glavnyi-tormoznoi-tsilindr")

    def test_remkomplekty_group_maps_clutch_cylinder_repair_kit(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Ремкомплекти", group="ERT", name="Ремкомплект головного циліндра зчеплення ERT")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "remkomplekt-tsilindra-stsepleniia")

    def test_clamps_group_maps_to_clamps_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Хомути, стяжки, затискачі", group="MASNER", name="Хомут черв'ячний MASNER")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "homuty-stiazhki-i-zazhimy")

    def test_gloves_group_maps_to_ppe_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Рукавички", group="DOLONI", name="Рукавички нітрилові DOLONI")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "sredstva-zashchity-i-spetsodezhda")

    def test_sponges_group_maps_to_sponges_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Серветки та губки", group="K2", name="Губка K2 для миття авто")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "gubki-i-salfetki-dlia-avto")

    def test_anticorrosion_group_maps_to_anticorrosion_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Антикорозійні засоби та покриття", group="Autotrade", name="Автоконсервант Пушсало Autotrade")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "antikorroziinye-sredstva-i-pokrytiia")

    def test_solvents_group_maps_to_solvents_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Розчинники", group="Autotrade", name="Змивка Антисиликон Autotrade")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "rastvoriteli-i-obezzhirivateli")

    def test_keys_group_maps_to_socket_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Ключі", group="YATO", name='Головка торцева YATO 1/2" 30 мм')]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "golovki-tortsevye")

    def test_pumps_group_maps_to_water_pump_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Насоси", group="AUTOMEGA", name="Насос водяний AUTOMEGA")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "vodianoi-nasos")

    def test_rollers_group_maps_to_drive_roller_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Ролики", group="CAFFARO", name="Ролик натяжний CAFFARO")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "rolik-remnia-privodnogo")

    def test_winter_tires_group_maps_to_winter_tires_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Шини зимові", group="GOODYEAR", name="Шина зимова GOODYEAR")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "zimnie-shiny")

    def test_summer_tires_group_maps_to_summer_tires_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Шини літні", group="MICHELIN", name="Шина літня MICHELIN")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "letnie-shiny")

    def test_all_season_tires_group_maps_to_all_season_tires_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Шини всесезонні", group="NOKIAN", name="Шина всесезонна NOKIAN")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "vsesezonnye-shiny")

    def test_body_polish_group_maps_to_body_polish_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Поліролі кузова", group="K2", name="Поліроль кузова K2 Wax")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "polirol-kuzova")

    def test_brush_scraper_group_maps_to_brush_scraper_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Щітки та шкребки", group="LAVITA", name="Шкребок для льоду LAVITA")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "shchetki-skrebki-i-vodosgony-dlia-avto")

    def test_shrksh_group_maps_to_shrus_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="ШРКШ", group="AT", name="ШРКШ внутрішній двобічний AT")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "shrus")

    def test_vkladyshi_group_maps_to_main_bearings_leaf(self):
        target = GplCategoryMappingAuditor().classify_row(
            row=_row(category="Вкладыши", group="AT", name="Вкладыши коренные AT")
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.slug, "vkladyshi-korennye")

    def test_fuel_pumps_group_maps_to_fuel_pump_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Насоси паливні", group="AT", name="Насос паливний AT")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "toplivnyi-nasos")

    def test_brake_cables_group_maps_to_parking_brake_cable_leaf(self):
        target = GplCategoryMappingAuditor().classify_row(
            row=_row(category="Тросы тормозной системы", group="AUTOMEGA", name="Трос ручника AUTOMEGA")
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.slug, "tros-ruchnika")

    def test_auto_cables_group_maps_to_throttle_cable_leaf(self):
        decision = GplCategoryMappingAuditor().decide_group(
            rows=[_row(category="Троси автомобільні", group="AT", name="Трос приводу акселератора AT")]
        )

        self.assertEqual(decision.status, STATUS_ACTIVE)
        self.assertEqual(decision.target_slug, "trosik-gaza")


class GplCategoryMappingCommandsTests(TestCase):
    def test_prioritize_gaps_command_exports_unresolved_rows(self):
        with TemporaryDirectory() as tmp_dir:
            audit_csv = Path(tmp_dir) / "audit.csv"
            export_csv = Path(tmp_dir) / "gaps.csv"
            audit_csv.write_text(
                "\n".join(
                    [
                        "raw_category,raw_group,product_count,top_brands,example_names,example_articles,proposed_root,proposed_leaf_category,proposed_leaf_slug,confidence,reason,status",
                        "Mapped,WIX,10,WIX:10,Example,ART,Root,Leaf,leaf,0.9,ok,active_mapping_candidate",
                        "Резонатори,POLMO,269,POLMO:269,Резонатор POLMO,01,Двигатель и выхлоп,,,0.0,low,needs_review",
                    ]
                ),
                encoding="utf-8",
            )

            out = StringIO()
            call_command("prioritize_gpl_category_mapping_gaps", "--audit-csv", str(audit_csv), "--export-csv", str(export_csv), stdout=out)

            self.assertTrue(export_csv.exists())
            self.assertIn("product_coverage_if_top_10_resolved", out.getvalue())
            self.assertIn("rezonator", export_csv.read_text(encoding="utf-8"))

    def test_web_reference_command_exports_confirmed_and_split_rows(self):
        with TemporaryDirectory() as tmp_dir:
            audit_csv = Path(tmp_dir) / "audit.csv"
            export_csv = Path(tmp_dir) / "web.csv"
            audit_csv.write_text(
                "\n".join(
                    [
                        "raw_category,raw_group,product_count,top_brands,example_names,example_articles,proposed_root,proposed_leaf_category,proposed_leaf_slug,confidence,reason,status",
                        "Тяги та наконечники,SPIDAN,270,SPIDAN:270,Наконечник рулевой тяги,ART,,,,0.0,missing,missing_leaf_category",
                        "Ароматизатори,K2,128,K2:128,Ароматизатор K2,ART,,,,0.0,missing,missing_leaf_category",
                    ]
                ),
                encoding="utf-8",
            )

            out = StringIO()
            call_command(
                "audit_gpl_unresolved_groups_with_web_reference",
                "--audit-csv",
                str(audit_csv),
                "--limit-groups",
                "50",
                "--export-csv",
                str(export_csv),
                stdout=out,
            )

            text = export_csv.read_text(encoding="utf-8")
            self.assertIn("split_needed", text)
            self.assertIn("confirmed_missing_leaf", text)
            self.assertIn("UTR calls=0", out.getvalue())

    def test_row_level_audit_command_exports_rows_for_unresolved_groups_only(self):
        with TemporaryDirectory() as tmp_dir:
            transmission_root = _root("transmission-row", "Сцепление и трансмиссия")
            care_root = _root("care-row", "Автохимия и аксессуары")
            _leaf(transmission_root, "remkomplekt-tsilindra-stsepleniia", "Ремкомплект цилиндра сцепления")
            _leaf(care_root, "rastvoriteli-i-obezzhirivateli", "Растворители и обезжириватели")

            price_csv = Path(tmp_dir) / "gpl-mini.csv"
            unresolved_csv = Path(tmp_dir) / "group-audit.csv"
            export_csv = Path(tmp_dir) / "row-audit.csv"
            missing_csv = Path(tmp_dir) / "row-missing.csv"
            draft_csv = Path(tmp_dir) / "row-draft.csv"

            price_csv.write_text(
                "\n".join(
                    [
                        "Категорія,Група ТД,Артикул ТД,Найменування,Опис",
                        "Ремкомплекти,ERT,200055,Ремкомплект головного циліндра зчеплення ERT,",
                        "Розчинники,Autotrade,SOLV1,Змивка Антисиликон Autotrade,",
                        "Повітряні фільтри,WIX FILTERS,AF1,Фільтр повітряний WIX,",
                    ]
                ),
                encoding="utf-8",
            )
            unresolved_csv.write_text(
                "\n".join(
                    [
                        "raw_category,raw_group,status,proposed_root,proposed_leaf_category,proposed_leaf_slug,reason",
                        "Ремкомплекти,ERT,missing_leaf_category,Сцепление и трансмиссия,,,missing",
                        "Розчинники,Autotrade,conflict,Автохимия и аксессуары,,,conflict",
                        "Повітряні фільтри,WIX FILTERS,active_mapping_candidate,Двигатель и выхлоп,Воздушный фильтр,vozdushnyi-filtr,ok",
                    ]
                ),
                encoding="utf-8",
            )

            out = StringIO()
            call_command(
                "audit_gpl_price_row_category_mapping",
                "--path",
                str(price_csv),
                "--export-csv",
                str(export_csv),
                "--unresolved-only-from",
                str(unresolved_csv),
                "--missing-leaf-csv",
                str(missing_csv),
                "--draft-csv",
                str(draft_csv),
                stdout=out,
            )

            self.assertTrue(export_csv.exists())
            rows = list(csv.DictReader(export_csv.open(encoding="utf-8")))
            self.assertEqual(len(rows), 2)
            by_key = {(row["raw_category"], row["raw_group"]): row for row in rows}
            self.assertEqual(by_key[("Ремкомплекти", "ERT")]["row_mapping_status"], "active_row_mapping")
            self.assertEqual(by_key[("Розчинники", "Autotrade")]["row_mapping_status"], "active_row_mapping")
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
