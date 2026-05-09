from __future__ import annotations

import re
import zlib
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.models import (
    Category,
    CategoryNavigationCollection,
    CategoryNavigationGroup,
    CategoryNavigationItem,
)
from apps.catalog.services.category_canonicalization import resolve_canonical_spec_for_name
from apps.catalog.services.category_management import find_category_by_normalized_name, normalized_category_name


@dataclass(frozen=True)
class TaxonomyLeafSpec:
    name: str
    slug: str = ""
    name_uk: str = ""
    name_ru: str = ""
    name_en: str = ""


@dataclass(frozen=True)
class TaxonomyGroupSpec:
    name: str
    slug: str
    leaves: tuple[TaxonomyLeafSpec | str, ...]


@dataclass(frozen=True)
class TaxonomyRootSpec:
    name: str
    slug: str
    name_uk: str = ""
    name_ru: str = ""
    name_en: str = ""
    groups: tuple[TaxonomyGroupSpec, ...] = ()


@dataclass(frozen=True)
class TaxonomyCollectionItemSpec:
    category_name: str
    title: str = ""


@dataclass(frozen=True)
class TaxonomyCollectionGroupSpec:
    name: str
    slug: str
    items: tuple[TaxonomyCollectionItemSpec | str, ...]


@dataclass(frozen=True)
class TaxonomyCollectionSpec:
    name: str
    slug: str
    root_slug: str
    groups: tuple[TaxonomyCollectionGroupSpec, ...]


@dataclass
class TaxonomySeedStats:
    roots_created: int = 0
    roots_updated: int = 0
    roots_unchanged: int = 0
    menu_groups_created: int = 0
    menu_groups_updated: int = 0
    menu_groups_unchanged: int = 0
    leaf_categories_created: int = 0
    leaf_categories_updated: int = 0
    leaf_categories_unchanged: int = 0
    navigation_links_created: int = 0
    navigation_links_updated: int = 0
    navigation_links_unchanged: int = 0
    duplicate_names: int = 0
    duplicate_slugs: int = 0
    invalid_assignable_parents: int = 0
    missing_navigation_targets: int = 0
    utr_calls: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "roots_created": self.roots_created,
            "roots_updated": self.roots_updated,
            "roots_unchanged": self.roots_unchanged,
            "menu_groups_created": self.menu_groups_created,
            "menu_groups_updated": self.menu_groups_updated,
            "menu_groups_unchanged": self.menu_groups_unchanged,
            "leaf_categories_created": self.leaf_categories_created,
            "leaf_categories_updated": self.leaf_categories_updated,
            "leaf_categories_unchanged": self.leaf_categories_unchanged,
            "navigation_links_created": self.navigation_links_created,
            "navigation_links_updated": self.navigation_links_updated,
            "navigation_links_unchanged": self.navigation_links_unchanged,
            "duplicate_names": self.duplicate_names,
            "duplicate_slugs": self.duplicate_slugs,
            "invalid_assignable_parents": self.invalid_assignable_parents,
            "missing_navigation_targets": self.missing_navigation_targets,
            "UTR calls": self.utr_calls,
        }


def leaf(name: str, *, slug: str = "", uk: str = "", ru: str = "", en: str = "") -> TaxonomyLeafSpec:
    return TaxonomyLeafSpec(name=name, slug=slug, name_uk=uk, name_ru=ru, name_en=en)


TAXONOMY_ROOT_SPECS: tuple[TaxonomyRootSpec, ...] = (
    TaxonomyRootSpec(name="Запчасти для ТО", slug="zapchasti-dlia-to"),
    TaxonomyRootSpec(
        name="Подвеска и рулевое",
        slug="podveska-i-rulevoe",
        groups=(
            TaxonomyGroupSpec(
                name="Подвеска",
                slug="podveska",
                leaves=(
                    leaf("Амортизаторы", slug="amortizatory"),
                    "Шаровые опоры",
                    "Рычаги и тяги",
                    "Пружины и рессоры",
                    "Опора амортизатора",
                    "Сайлентблоки",
                    "Пыльники и отбойники амортизаторов",
                    "Прокладка пружины",
                    "Рессоры",
                    "Втулка рессоры",
                    "Опорный подшипник",
                    "Сайлентблок амортизатора",
                    "Сайлентблоки задней балки",
                ),
            ),
            TaxonomyGroupSpec(
                name="Стабилизатор и ступица",
                slug="stabilizator-i-stupitsa",
                leaves=(
                    "Стойки стабилизатора",
                    "Втулки стабилизатора",
                    "Скоба стабилизатора",
                    "Подшипник ступицы",
                    "Ступица",
                    "Поворотный кулак",
                    "Гайка ступицы",
                ),
            ),
            TaxonomyGroupSpec(
                name="Рулевое управление",
                slug="rulevoe-upravlenie",
                leaves=(
                    "Рулевые наконечники",
                    "Рулевые тяги",
                    "Насос гидроусилителя",
                    "Рулевая рейка и крепление",
                    "Кардан рулевого вала",
                    "Пыльник рулевой тяги",
                    "Маятник рулевой",
                    "Шланг ГУР",
                ),
            ),
        ),
    ),
    TaxonomyRootSpec(
        name="Тормозная система",
        slug="tormoznaia-sistema",
        groups=(
            TaxonomyGroupSpec(
                name="Популярное",
                slug="popularnoe",
                leaves=(
                    leaf("Тормозные колодки", slug="tormoznye-kolodki"),
                    "Тормозные диски",
                    "Трос ручника",
                    "Тросы тормозной системы",
                    "Ремкомплект суппорта",
                    "Тормозной суппорт",
                ),
            ),
            TaxonomyGroupSpec(
                name="Гидравлика",
                slug="gidravlika",
                leaves=(
                    "Вакуумный усилитель тормозов",
                    "Тормозной шланг",
                    "Главный тормозной цилиндр",
                    "Рабочий тормозной цилиндр",
                ),
            ),
            TaxonomyGroupSpec(
                name="Датчики и крепеж",
                slug="datchiki-i-krepezh",
                leaves=(
                    "Ремкомплект тормозных колодок",
                    "Отражатель тормозного диска",
                    "Ремкомплект стояночного тормоза",
                    "Датчик ABS",
                    "Датчик износа тормозных колодок",
                    "Датчик стоп сигнала",
                    "Кольцо ABS",
                ),
            ),
        ),
    ),
    TaxonomyRootSpec(
        name="Охлаждение и отопление",
        slug="okhlazhdenie-i-otoplenie",
        groups=(
            TaxonomyGroupSpec(
                name="Охлаждение двигателя",
                slug="okhlazhdenie-dvigatelia",
                leaves=(
                    "Радиатор охлаждения двигателя",
                    "Вентилятор охлаждения двигателя",
                    "Водяной насос",
                    "Термостат",
                    "Масляный радиатор",
                    "Расширительный бачок",
                    "Корпус термостата",
                    "Датчик температуры охлаждающей жидкости",
                    "Крышка расширительного бачка",
                    "Патрубок радиатора охлаждения",
                    "Крышка радиатора",
                    "Термовыключатель вентилятора радиатора",
                    "Подушка радиатора",
                    "Прокладка термостата",
                    "Прокладка корпуса термостата",
                ),
            ),
            TaxonomyGroupSpec(
                name="Кондиционер",
                slug="konditsioner",
                leaves=(
                    "Радиатор кондиционера",
                    "Компрессор кондиционера",
                    "Шкив компрессора кондиционера",
                ),
            ),
            TaxonomyGroupSpec(
                name="Отопление",
                slug="otoplenie",
                leaves=(
                    "Радиатор печки",
                    "Вентилятор печки",
                    "Кран печки",
                    "Патрубок радиатора печки",
                ),
            ),
        ),
    ),
    TaxonomyRootSpec(
        name="Двигатель и выхлоп",
        slug="dvigatel-i-vykhlop",
        groups=(
            TaxonomyGroupSpec(
                name="Детали двигателя",
                slug="detali-dvigatelia",
                leaves=(
                    "Кольца поршневые",
                    "Поршня",
                    "Клапана впускные",
                    "Клапана выпускные",
                    "Сальники клапанов",
                    "Гидрокомпенсаторы",
                    "Распредвал",
                    "Сальник распредвала",
                    "Сальник коленвала",
                    "Шкив коленвала / Демпфер",
                    "Масляный насос",
                    "Вкладыши коренные",
                    "Вкладыши шатунные",
                    "Подушки двигателя",
                    "Втулка шатуна",
                    "Масляный поддон двигателя",
                    "Пробка масляного поддона",
                    "Крышка маслозаливной горловины",
                    "Масляный щуп",
                    "Крышка клапанов",
                    "Шестерня коленвала",
                    "Шестерня распредвала",
                    "Клапан давления масла",
                    "Болт ГБЦ",
                    "Заглушка блока цилиндров",
                    "Воронка шума масла",
                    "Болт шкива коленвала",
                    "Педаль газа",
                ),
            ),
            TaxonomyGroupSpec(
                name="Ремни, цепи, натяжители",
                slug="remni-tsepi-natiazhiteli",
                leaves=(
                    "Комплект ГРМ",
                    "Ремень ГРМ",
                    "Натяжитель ремня ГРМ",
                    "Ремень приводной",
                    "Ролик ремня приводного",
                    "Цепь ГРМ",
                    "Комплект приводного ремня",
                    "Ролик ГРМ",
                    "Натяжитель приводного ремня",
                    "Кожух ремня ГРМ",
                ),
            ),
            TaxonomyGroupSpec(
                name="Фильтры",
                slug="filtry",
                leaves=(
                    leaf("Воздушный фильтр", slug="vozdushnyi-filtr"),
                    leaf("Масляный фильтр", slug="maslianyi-filtr"),
                    leaf("Топливный фильтр", slug="toplivnyi-filtr"),
                    leaf("Фильтр салона", slug="filtr-salona"),
                    "Комплект фильтров",
                ),
            ),
            TaxonomyGroupSpec(
                name="Прокладки",
                slug="prokladki",
                leaves=(
                    "Прокладка ГБЦ",
                    "Прокладка клапанной крышки",
                    "Прокладка впускного коллектора",
                    "Прокладка теплообменника",
                    "Прокладка масляного насоса",
                    "Уплотнительное кольцо пробки поддона",
                    "Прокладка поддона",
                    "Комплект прокладок двигателя",
                    "Комплект прокладок ГБЦ",
                    "Прокладка корпуса масляного фильтра",
                ),
            ),
            TaxonomyGroupSpec(
                name="Топливная система",
                slug="toplivnaia-sistema",
                leaves=(
                    "Топливный насос",
                    "Турбина",
                    "Интеркулер",
                    "Ремкомплект турбины",
                    "Датчик давления наддува турбины",
                ),
            ),
            TaxonomyGroupSpec(
                name="Система выпуска",
                slug="sistema-vypuska",
                leaves=(
                    leaf("Глушитель", slug="glushitel"),
                    leaf("Резонатор", slug="rezonator"),
                    leaf("Приемная труба", slug="priemnaia-truba"),
                    leaf("Трубы выхлопной системы", slug="truby-vykhlopnoi-sistemy"),
                    "Катализатор",
                    "Гофра выхлопной системы",
                    "Клапан рециркуляции отработанных газов",
                    "Шланг вентиляции картера",
                    "Датчик давления выхлопных газов",
                    "Прокладка глушителя",
                    "Подвес глушителя",
                    "Хомут глушителя",
                    "Сажевый фильтр",
                ),
            ),
        ),
    ),
    TaxonomyRootSpec(
        name="Сцепление и трансмиссия",
        slug="stseplenie-i-transmissiia",
        groups=(
            TaxonomyGroupSpec(
                name="Сцепление",
                slug="stseplenie",
                leaves=(
                    "Комплект сцепления",
                    "Диск сцепления",
                    "Выжимной подшипник",
                    "Маховик",
                    "Главный цилиндр сцепления",
                    "Рабочий цилиндр сцепления",
                    "Ремкомплект цилиндра сцепления",
                    "Накладка педали сцепления",
                ),
            ),
            TaxonomyGroupSpec(
                name="Приводы",
                slug="privody",
                leaves=(
                    "ШРУС",
                    "Полуось",
                    "Пыльник ШРУСа",
                ),
            ),
            TaxonomyGroupSpec(
                name="КПП и трансмиссия",
                slug="kpp-i-transmissiia",
                leaves=(
                    "Масляный фильтр АКПП",
                    "Сальники",
                    "Подушки крепления КПП",
                    "Прокладки КПП",
                    "Кулиса",
                    "Датчик скорости",
                    "Тросик спидометра",
                    "Сальник КПП",
                    "Ручка кулисы КПП",
                    "Подшипник КПП",
                    "Датчик оборотов АКПП",
                    "Сальник раздатки",
                ),
            ),
            TaxonomyGroupSpec(
                name="Кардан и редуктор",
                slug="kardan-i-reduktor",
                leaves=(
                    "Крестовина карданного вала",
                    "Подушка раздатки",
                    "Подшипник редуктора",
                ),
            ),
        ),
    ),
    TaxonomyRootSpec(
        name="Электрика и освещение",
        slug="elektrika-i-osveshchenie",
        groups=(
            TaxonomyGroupSpec(
                name="Популярное",
                slug="popularnoe",
                leaves=(
                    leaf("Аккумуляторы", slug="akkumuliatory"),
                    "Автолампы",
                    "Свечи зажигания",
                    "Свечи накала",
                    "Генератор",
                    "Стартер",
                ),
            ),
            TaxonomyGroupSpec(
                name="Автосвет",
                slug="avtosvet",
                leaves=(
                    "Противотуманки",
                    "Фара основная",
                    "Указатели поворота",
                    "Задний фонарь",
                    "Корректор фар",
                    "Фонарь подсветки номера",
                    "Задний противотуманный фонарь",
                    "Дополнительный стоп сигнал",
                    "Повторитель поворота",
                    "Отражатель",
                ),
            ),
            TaxonomyGroupSpec(
                name="Зажигание",
                slug="zazhiganie",
                leaves=(
                    "Свечи накаливания",
                    "Провода высоковольтные",
                    "Катушка зажигания",
                    "Трамблер",
                    "Бегунок трамблера",
                    "Крышка трамблера",
                    "Наконечник катушки зажигания",
                ),
            ),
            TaxonomyGroupSpec(
                name="Электрика",
                slug="elektrika",
                leaves=(
                    "Бендикс стартера",
                    "Втягивающее реле стартера",
                    "Щетка стартера",
                    "Реле регулятор генератора",
                    "Реле ВСЕ",
                    "Подрулевые переключатели",
                    "Обгонная муфта генератора",
                    "Звуковой сигнал",
                    "Выключатель головного света",
                    "Замок зажигания",
                    "Кнопка аварийки",
                    "Щетки генератора",
                    "Диодный мост генератора",
                    "Реле стартера",
                    "Токосъемные кольца генератора",
                    "Ремкомплект стартера",
                    "Датчик парктроника",
                    "Кнопка стеклоподъемника",
                    "Антенна автомобильная",
                ),
            ),
            TaxonomyGroupSpec(
                name="Система стеклоочистителя",
                slug="sistema-stekloochistitelia",
                leaves=(
                    "Трапеция стеклоочистителя",
                    "Поводок стеклоочистителя",
                    "Форсунки омывателя стекла",
                ),
            ),
        ),
    ),
    TaxonomyRootSpec(
        name="Детали кузова",
        slug="detali-kuzova",
        groups=(
            TaxonomyGroupSpec(
                name="Наружные части",
                slug="naruzhnye-chasti",
                leaves=(
                    "Бампер",
                    "Усилитель бампера",
                    "Решетка радиатора",
                    "Боковое зеркало",
                    "Подкрылки",
                    "Заглушка буксировочного крюка",
                    "Молдинг бампера",
                    "Элемент бокового зеркала",
                    "Корпус бокового зеркала",
                    "Фаркоп",
                    "Кронштейн бампера",
                    "Крепление капота",
                ),
            ),
            TaxonomyGroupSpec(
                name="Внутренние элементы",
                slug="vnutrennie-elementy",
                leaves=(
                    "Ручка двери",
                    "Личинка замка автомобиля",
                    "Газовый амортизатор капота",
                    "Стеклоподъемник",
                    "Шумоизоляция двигателя",
                    "Защита двигателя",
                    "Крепление защиты двигателя",
                    "Ограничитель двери",
                    "Задняя панель",
                    "Сайлентблоки подрамника",
                    "Ролики сдвижной двери",
                    "Газовый амортизатор багажника",
                    "Коврик салона",
                    "Коврик в багажник",
                    "Центральный замок",
                    "Замок двери",
                    "Замок багажника",
                ),
            ),
            TaxonomyGroupSpec(
                name="Система стеклоочистителя",
                slug="sistema-stekloochistitelia",
                leaves=(
                    "Дворники",
                    "Бачок омывателя",
                    "Насос бачка омывателя",
                ),
            ),
            TaxonomyGroupSpec(
                name="Тросики",
                slug="trosiki",
                leaves=(
                    "Тросик газа",
                    "Тросик сцепления",
                    "Трос замка двери",
                ),
            ),
        ),
    ),
    TaxonomyRootSpec(
        name="Колёса и шины",
        slug="kolesa-i-shiny",
        name_uk="Колеса та шини",
        name_ru="Колёса и шины",
        name_en="Wheels and tires",
        groups=(
            TaxonomyGroupSpec(
                name="Шины",
                slug="shiny",
                leaves=(
                    leaf("Зимние шины", slug="zimnie-shiny", uk="Зимові шини", ru="Зимние шины", en="Winter tires"),
                    leaf("Летние шины", slug="letnie-shiny", uk="Літні шини", ru="Летние шины", en="Summer tires"),
                    leaf("Всесезонные шины", slug="vsesezonnye-shiny", uk="Всесезонні шини", ru="Всесезонные шины", en="All-season tires"),
                ),
            ),
            TaxonomyGroupSpec(
                name="Колёса и крепеж",
                slug="kolesa-i-krepezh",
                leaves=(
                    leaf("Секретки на колёса", slug="sekretki-na-kolesa"),
                    leaf("Болты и гайки колёс", slug="bolty-i-gaiki-koles", uk="Болти та гайки коліс", ru="Болты и гайки колёс", en="Wheel bolts and nuts"),
                ),
            ),
            TaxonomyGroupSpec(
                name="Датчики и аксессуары",
                slug="datchiki-i-aksessuary",
                leaves=(
                    leaf("Датчик давления в шине", slug="datchik-davleniia-v-shine"),
                    leaf("Цепи противоскольжения", slug="tsepi-protivoskolzheniia"),
                ),
            ),
        ),
    ),
    TaxonomyRootSpec(
        name="Автохимия и аксессуары",
        slug="avtohimiia-i-aksessuary",
        groups=(
            TaxonomyGroupSpec(
                name="Масла",
                slug="masla",
                leaves=(
                    leaf("Моторное масло", slug="motornoe-maslo"),
                    "Моторное масло для 2-тактного двигателя",
                    "Моторное масло для 4-тактного двигателя",
                    "Масло трансмиссионное",
                    "Масло ГУР",
                    "Гидравлическое масло",
                    "Смазка",
                ),
            ),
            TaxonomyGroupSpec(
                name="Автохимия",
                slug="avtohimiia",
                leaves=(
                    "Жидкость тормозная",
                    "Антифриз",
                    "Герметики",
                    "Очистители кондиционера",
                    "Присадки",
                    "Уход за авто",
                    leaf("Полироли кузова", slug="polirol-kuzova"),
                    leaf("Ароматизаторы", slug="aromatizatory"),
                    leaf("Бытовая химия", slug="bytovaia-khimiia"),
                    "Губки и салфетки для авто",
                    "Антикоррозийные средства и покрытия",
                    "Растворители и обезжириватели",
                    "AdBlue и технические жидкости",
                    "Автоэмали и краски",
                    "Аэрозольные краски",
                    "Грунты и лаки",
                    "Изолента и электроматериалы",
                ),
            ),
            TaxonomyGroupSpec(
                name="Техническая помощь",
                slug="tehnicheskaia-pomoshch",
                leaves=(
                    "Автомобильные тенты",
                    "Щетки, скребки и водосгоны для авто",
                    "Средства защиты и спецодежда",
                    "Хомуты, стяжки и зажимы",
                    "Огнетушители",
                    "Домкраты",
                    "Знак аварийной остановки",
                    "Клеммы аккумулятора",
                    "Батарейки",
                    "Аптечки и безопасность",
                ),
            ),
            TaxonomyGroupSpec(
                name="Инструменты",
                slug="instrumenty",
                leaves=(
                    "Ящик для инструментов",
                    "Воротки",
                    "Динамометрические ключи",
                    "Головки торцевые",
                    "Органайзеры",
                ),
            ),
            TaxonomyGroupSpec(
                name="Для перевозки груза",
                slug="dlia-perevozki-gruza",
                leaves=(),
            ),
        ),
    ),
)

TO_COLLECTION_SPEC = TaxonomyCollectionSpec(
    name="Запчасти для ТО",
    slug="zapchasti-dlia-to",
    root_slug="zapchasti-dlia-to",
    groups=(
        TaxonomyCollectionGroupSpec(
            name="Электрика",
            slug="elektrika",
            items=(
                "Аккумуляторы",
                "Свечи зажигания",
                "Свечи накала",
                TaxonomyCollectionItemSpec(category_name="Автолампы", title="Лампы"),
            ),
        ),
        TaxonomyCollectionGroupSpec(
            name="Фильтры",
            slug="filtry",
            items=(
                "Масляный фильтр",
                "Воздушный фильтр",
                "Фильтр салона",
                "Топливный фильтр",
            ),
        ),
        TaxonomyCollectionGroupSpec(
            name="ТО двигателя",
            slug="to-dvigatelia",
            items=(
                "Ремень ГРМ",
                "Комплект ГРМ",
                "Натяжитель ремня ГРМ",
                TaxonomyCollectionItemSpec(category_name="Водяной насос", title="Помпа"),
                "Ремень приводной",
                TaxonomyCollectionItemSpec(category_name="Ролик ремня приводного", title="Ролик приводного ремня"),
                "Термостат",
                TaxonomyCollectionItemSpec(category_name="Моторное масло", title="Масло моторное"),
            ),
        ),
        TaxonomyCollectionGroupSpec(
            name="ТО тормозной системы",
            slug="to-tormoznoi-sistemy",
            items=(
                "Тормозные колодки",
                "Тормозные диски",
            ),
        ),
        TaxonomyCollectionGroupSpec(
            name="ТО ходовой части",
            slug="to-hodovoi-chasti",
            items=(
                TaxonomyCollectionItemSpec(category_name="Рулевые наконечники", title="Рулевая тяга и наконечник"),
            ),
        ),
    ),
)


def iter_taxonomy_leaf_specs() -> tuple[TaxonomyLeafSpec, ...]:
    leaves: list[TaxonomyLeafSpec] = []
    for root in TAXONOMY_ROOT_SPECS:
        for group in root.groups:
            for raw_leaf in group.leaves:
                leaves.append(_coerce_leaf(raw_leaf))
    return tuple(leaves)


def build_taxonomy_leaf_name_map() -> dict[str, TaxonomyLeafSpec]:
    out: dict[str, TaxonomyLeafSpec] = {}
    for spec in iter_taxonomy_leaf_specs():
        key = normalized_category_name(spec.name)
        if key and key not in out:
            out[key] = spec
    return out


def find_seeded_leaf_by_name(name: str) -> Category | None:
    key = normalized_category_name(name)
    if not key:
        return None
    spec = build_taxonomy_leaf_name_map().get(key)
    canonical = resolve_canonical_spec_for_name(name)
    if spec is None and canonical is not None:
        category = Category.objects.filter(slug=canonical.canonical_slug, is_assignable=True, is_active=True).first()
        if category is not None:
            return category
    if spec is not None:
        slug = _leaf_slug(spec)
        category = Category.objects.filter(slug=slug, is_assignable=True, is_active=True).first()
        if category is not None:
            return category
    category = find_category_by_normalized_name(name=name, parent=None)
    if category is not None and category.is_assignable:
        return category
    for candidate in Category.objects.filter(is_active=True, is_assignable=True).only("id", "name", "name_uk", "name_ru", "name_en", "slug"):
        values = {
            normalized_category_name(candidate.name),
            normalized_category_name(candidate.name_uk),
            normalized_category_name(candidate.name_ru),
            normalized_category_name(candidate.name_en),
        }
        if key in values:
            return candidate
    return None


class TaxonomyV2Seeder:
    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.now = timezone.now()
        self.stats = TaxonomySeedStats()
        self._roots_by_slug: dict[str, Category] = {}
        self._groups_by_key: dict[tuple[str, str], Category] = {}
        self._leaves_by_name: dict[str, Category] = {}

    def seed(self) -> TaxonomySeedStats:
        if self.dry_run:
            return self._seed_dry_run()

        with transaction.atomic():
            for index, root_spec in enumerate(TAXONOMY_ROOT_SPECS, start=1):
                root = self._upsert_category(
                    spec_name=root_spec.name,
                    slug=root_spec.slug,
                    parent=None,
                    sort_order=index * 10,
                    show_in_header=True,
                    is_assignable=False,
                    bucket="roots",
                    name_uk=root_spec.name_uk,
                    name_ru=root_spec.name_ru,
                    name_en=root_spec.name_en,
                )
                self._roots_by_slug[root_spec.slug] = root
                for group_index, group_spec in enumerate(root_spec.groups, start=1):
                    group = self._upsert_category(
                        spec_name=group_spec.name,
                        slug=f"{root_spec.slug}-{group_spec.slug}",
                        parent=root,
                        sort_order=group_index * 10,
                        show_in_header=False,
                        is_assignable=False,
                        bucket="menu_groups",
                    )
                    self._groups_by_key[(root_spec.slug, group_spec.slug)] = group
                    for leaf_index, raw_leaf in enumerate(group_spec.leaves, start=1):
                        leaf_spec = _coerce_leaf(raw_leaf)
                        leaf_category = self._upsert_category(
                            spec_name=leaf_spec.name,
                            slug=_leaf_slug(leaf_spec),
                            parent=group,
                            sort_order=leaf_index * 10,
                            show_in_header=False,
                            is_assignable=True,
                            bucket="leaf_categories",
                            name_uk=leaf_spec.name_uk,
                            name_ru=leaf_spec.name_ru,
                            name_en=leaf_spec.name_en,
                        )
                        self._leaves_by_name[normalized_category_name(leaf_spec.name)] = leaf_category

            self._seed_collection(TO_COLLECTION_SPEC)
            self._refresh_integrity_stats()
        return self.stats

    def _seed_dry_run(self) -> TaxonomySeedStats:
        existing_roots = {item.slug: item for item in Category.objects.filter(parent__isnull=True)}
        existing_categories = {item.slug: item for item in Category.objects.all()}
        existing_collections = {
            item.slug: item for item in CategoryNavigationCollection.objects.select_related("root_category").all()
        }
        existing_groups = {
            (item.collection.slug, item.slug): item
            for item in CategoryNavigationGroup.objects.select_related("collection").all()
        }
        existing_items = {
            (item.group.collection.slug, item.group.slug, item.category.slug): item
            for item in CategoryNavigationItem.objects.select_related("group__collection", "category").all()
        }

        virtual_leaf_slugs: set[str] = set()
        for index, root_spec in enumerate(TAXONOMY_ROOT_SPECS, start=1):
            root = existing_roots.get(root_spec.slug) or existing_categories.get(root_spec.slug)
            self._count_category_state(
                existing=root,
                name=root_spec.name,
                slug=root_spec.slug,
                sort_order=index * 10,
                show_in_header=True,
                is_assignable=False,
                bucket="roots",
            )
            for group_index, group_spec in enumerate(root_spec.groups, start=1):
                group_slug = f"{root_spec.slug}-{group_spec.slug}"
                group = existing_categories.get(group_slug)
                self._count_category_state(
                    existing=group,
                    name=group_spec.name,
                    slug=group_slug,
                    sort_order=group_index * 10,
                    show_in_header=False,
                    is_assignable=False,
                    bucket="menu_groups",
                )
                for leaf_index, raw_leaf in enumerate(group_spec.leaves, start=1):
                    leaf_spec = _coerce_leaf(raw_leaf)
                    leaf_slug = _leaf_slug(leaf_spec)
                    virtual_leaf_slugs.add(leaf_slug)
                    self._count_category_state(
                        existing=existing_categories.get(leaf_slug),
                        name=leaf_spec.name,
                        slug=leaf_slug,
                        sort_order=leaf_index * 10,
                        show_in_header=False,
                        is_assignable=True,
                        bucket="leaf_categories",
                    )

        collection = existing_collections.get(TO_COLLECTION_SPEC.slug)
        if collection is None:
            self.stats.navigation_links_created += 1
        elif self._collection_needs_update(collection, TO_COLLECTION_SPEC):
            self.stats.navigation_links_updated += 1
        else:
            self.stats.navigation_links_unchanged += 1

        for group_index, group_spec in enumerate(TO_COLLECTION_SPEC.groups, start=1):
            nav_group = existing_groups.get((TO_COLLECTION_SPEC.slug, group_spec.slug))
            if nav_group is None:
                self.stats.navigation_links_created += 1
            elif self._nav_group_needs_update(nav_group, group_spec, group_index * 10):
                self.stats.navigation_links_updated += 1
            else:
                self.stats.navigation_links_unchanged += 1

            for item_index, raw_item in enumerate(group_spec.items, start=1):
                item_spec = _coerce_collection_item(raw_item)
                target_slug = self._target_slug_for_collection_item(item_spec)
                if not target_slug:
                    self.stats.missing_navigation_targets += 1
                    continue
                existing = existing_items.get((TO_COLLECTION_SPEC.slug, group_spec.slug, target_slug))
                if existing is None:
                    self.stats.navigation_links_created += 1
                elif self._nav_item_needs_update(existing, item_spec, item_index * 10):
                    self.stats.navigation_links_updated += 1
                else:
                    self.stats.navigation_links_unchanged += 1

        self._refresh_integrity_stats()
        if not Category.objects.exists():
            self.stats.duplicate_names = 0
            self.stats.duplicate_slugs = 0
            self.stats.invalid_assignable_parents = 0
        return self.stats

    def _seed_collection(self, spec: TaxonomyCollectionSpec) -> None:
        root = self._roots_by_slug.get(spec.root_slug) or Category.objects.filter(slug=spec.root_slug).first()
        collection, created = CategoryNavigationCollection.objects.get_or_create(
            slug=spec.slug,
            defaults={
                "title": spec.name,
                "title_uk": spec.name,
                "title_ru": spec.name,
                "title_en": "",
                "root_category": root,
                "show_in_header": True,
                "sort_order": 10,
                "is_active": True,
                "published_at": self.now,
            },
        )
        if created:
            self.stats.navigation_links_created += 1
        else:
            updates: list[str] = []
            if collection.title != spec.name:
                collection.title = spec.name
                updates.append("title")
            if collection.title_uk != spec.name:
                collection.title_uk = spec.name
                updates.append("title_uk")
            if collection.title_ru != spec.name:
                collection.title_ru = spec.name
                updates.append("title_ru")
            if collection.root_category_id != getattr(root, "id", None):
                collection.root_category = root
                updates.append("root_category")
            if not collection.show_in_header:
                collection.show_in_header = True
                updates.append("show_in_header")
            if collection.sort_order != 10:
                collection.sort_order = 10
                updates.append("sort_order")
            if not collection.is_active:
                collection.is_active = True
                updates.append("is_active")
            self._save_or_count(collection, updates, created_bucket="navigation_links")

        for group_index, group_spec in enumerate(spec.groups, start=1):
            group, group_created = CategoryNavigationGroup.objects.get_or_create(
                collection=collection,
                slug=group_spec.slug,
                defaults={
                    "title": group_spec.name,
                    "title_uk": group_spec.name,
                    "title_ru": group_spec.name,
                    "title_en": "",
                    "sort_order": group_index * 10,
                    "is_active": True,
                    "published_at": self.now,
                },
            )
            if group_created:
                self.stats.navigation_links_created += 1
            else:
                updates = []
                if group.title != group_spec.name:
                    group.title = group_spec.name
                    updates.append("title")
                if group.title_uk != group_spec.name:
                    group.title_uk = group_spec.name
                    updates.append("title_uk")
                if group.title_ru != group_spec.name:
                    group.title_ru = group_spec.name
                    updates.append("title_ru")
                if group.sort_order != group_index * 10:
                    group.sort_order = group_index * 10
                    updates.append("sort_order")
                if not group.is_active:
                    group.is_active = True
                    updates.append("is_active")
                self._save_or_count(group, updates, created_bucket="navigation_links")

            for item_index, raw_item in enumerate(group_spec.items, start=1):
                item_spec = _coerce_collection_item(raw_item)
                category = self._target_category_for_collection_item(item_spec)
                if category is None:
                    self.stats.missing_navigation_targets += 1
                    continue
                item, item_created = CategoryNavigationItem.objects.get_or_create(
                    group=group,
                    category=category,
                    defaults={
                        "title_override": item_spec.title,
                        "title_override_uk": item_spec.title,
                        "title_override_ru": item_spec.title,
                        "title_override_en": "",
                        "sort_order": item_index * 10,
                        "is_active": True,
                        "published_at": self.now,
                    },
                )
                if item_created:
                    self.stats.navigation_links_created += 1
                    continue
                updates = []
                if item.title_override != item_spec.title:
                    item.title_override = item_spec.title
                    updates.append("title_override")
                if item.title_override_uk != item_spec.title:
                    item.title_override_uk = item_spec.title
                    updates.append("title_override_uk")
                if item.title_override_ru != item_spec.title:
                    item.title_override_ru = item_spec.title
                    updates.append("title_override_ru")
                if item.sort_order != item_index * 10:
                    item.sort_order = item_index * 10
                    updates.append("sort_order")
                if not item.is_active:
                    item.is_active = True
                    updates.append("is_active")
                self._save_or_count(item, updates, created_bucket="navigation_links")

    def _upsert_category(
        self,
        *,
        spec_name: str,
        slug: str,
        parent: Category | None,
        sort_order: int,
        show_in_header: bool,
        is_assignable: bool,
        bucket: str,
        name_uk: str = "",
        name_ru: str = "",
        name_en: str = "",
    ) -> Category:
        category = Category.objects.filter(slug=slug).first()
        if category is None:
            category = find_category_by_normalized_name(name=spec_name, parent=parent)
        if category is None:
            category = Category.objects.create(
                name=spec_name,
                name_uk=name_uk or spec_name,
                name_ru=name_ru or spec_name,
                name_en=name_en,
                slug=slug,
                parent=parent,
                source=Category.SOURCE_MANUAL,
                show_in_header=show_in_header,
                sort_order=sort_order,
                is_assignable=is_assignable,
                is_active=True,
                published_at=self.now,
            )
            self._increment(bucket, "created")
            return category

        updates: list[str] = []
        if category.name != spec_name:
            category.name = spec_name
            updates.append("name")
        if category.name_uk != (name_uk or spec_name):
            category.name_uk = name_uk or spec_name
            updates.append("name_uk")
        if category.name_ru != (name_ru or spec_name):
            category.name_ru = name_ru or spec_name
            updates.append("name_ru")
        if name_en and category.name_en != name_en:
            category.name_en = name_en
            updates.append("name_en")
        if category.slug != slug and not Category.objects.filter(slug=slug).exclude(id=category.id).exists():
            category.slug = slug
            updates.append("slug")
        if category.parent_id != getattr(parent, "id", None):
            category.parent = parent
            updates.append("parent")
        if category.source != Category.SOURCE_MANUAL:
            category.source = Category.SOURCE_MANUAL
            updates.append("source")
        if category.show_in_header != show_in_header:
            category.show_in_header = show_in_header
            updates.append("show_in_header")
        if category.sort_order != sort_order:
            category.sort_order = sort_order
            updates.append("sort_order")
        if category.is_assignable != is_assignable:
            category.is_assignable = is_assignable
            updates.append("is_assignable")
        if not category.is_active:
            category.is_active = True
            updates.append("is_active")
        if category.published_at is None:
            category.published_at = self.now
            updates.append("published_at")
        self._save_or_count(category, updates, created_bucket=bucket)
        return category

    def _count_category_state(
        self,
        *,
        existing: Category | None,
        name: str,
        slug: str,
        sort_order: int,
        show_in_header: bool,
        is_assignable: bool,
        bucket: str,
    ) -> None:
        if existing is None:
            self._increment(bucket, "created")
            return
        changed = (
            existing.name != name
            or existing.slug != slug
            or existing.sort_order != sort_order
            or existing.show_in_header != show_in_header
            or existing.is_assignable != is_assignable
            or not existing.is_active
            or existing.source != Category.SOURCE_MANUAL
        )
        self._increment(bucket, "updated" if changed else "unchanged")

    def _save_or_count(self, obj, updates: list[str], *, created_bucket: str) -> None:
        if updates:
            obj.save(update_fields=tuple(dict.fromkeys([*updates, "updated_at"])))
            self._increment(created_bucket, "updated")
            return
        self._increment(created_bucket, "unchanged")

    def _increment(self, bucket: str, state: str) -> None:
        field_name = f"{bucket}_{state}"
        setattr(self.stats, field_name, getattr(self.stats, field_name) + 1)

    def _target_category_for_collection_item(self, item: TaxonomyCollectionItemSpec) -> Category | None:
        key = normalized_category_name(item.category_name)
        category = self._leaves_by_name.get(key)
        if category is not None and category.is_assignable:
            return category
        return find_seeded_leaf_by_name(item.category_name)

    def _target_slug_for_collection_item(self, item: TaxonomyCollectionItemSpec) -> str:
        key = normalized_category_name(item.category_name)
        spec = build_taxonomy_leaf_name_map().get(key)
        if spec is None:
            return ""
        return _leaf_slug(spec)

    @staticmethod
    def _collection_needs_update(collection: CategoryNavigationCollection, spec: TaxonomyCollectionSpec) -> bool:
        return (
            collection.title != spec.name
            or collection.title_uk != spec.name
            or collection.title_ru != spec.name
            or not collection.show_in_header
            or not collection.is_active
        )

    @staticmethod
    def _nav_group_needs_update(group: CategoryNavigationGroup, spec: TaxonomyCollectionGroupSpec, sort_order: int) -> bool:
        return (
            group.title != spec.name
            or group.title_uk != spec.name
            or group.title_ru != spec.name
            or group.sort_order != sort_order
            or not group.is_active
        )

    @staticmethod
    def _nav_item_needs_update(item: CategoryNavigationItem, spec: TaxonomyCollectionItemSpec, sort_order: int) -> bool:
        return (
            item.title_override != spec.title
            or item.title_override_uk != spec.title
            or item.title_override_ru != spec.title
            or item.sort_order != sort_order
            or not item.is_active
        )

    def _refresh_integrity_stats(self) -> None:
        self.stats.duplicate_slugs = Category.objects.values("slug").annotate(total=Count("id")).filter(total__gt=1).count()
        self.stats.duplicate_names = count_duplicate_category_names_same_parent()
        self.stats.invalid_assignable_parents = count_invalid_assignable_parents()


def count_duplicate_category_names_same_parent() -> int:
    seen: set[tuple[str, str]] = set()
    duplicates: set[tuple[str, str]] = set()
    for category in Category.objects.filter(is_active=True).only("id", "name", "parent_id").iterator(chunk_size=1000):
        key = (str(category.parent_id or ""), normalized_category_name(category.name))
        if not key[1]:
            continue
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return len(duplicates)


def count_invalid_assignable_parents() -> int:
    parent_ids = set(
        Category.objects.filter(parent_id__isnull=False, is_active=True).values_list("parent_id", flat=True)
    )
    return Category.objects.filter(is_active=True, is_assignable=True).filter(parent__isnull=True).count() + Category.objects.filter(
        is_active=True,
        is_assignable=True,
        id__in=parent_ids,
    ).count()


def _coerce_leaf(value: TaxonomyLeafSpec | str) -> TaxonomyLeafSpec:
    if isinstance(value, TaxonomyLeafSpec):
        return value
    return TaxonomyLeafSpec(name=value)


def _coerce_collection_item(value: TaxonomyCollectionItemSpec | str) -> TaxonomyCollectionItemSpec:
    if isinstance(value, TaxonomyCollectionItemSpec):
        return value
    return TaxonomyCollectionItemSpec(category_name=value)


def _leaf_slug(spec: TaxonomyLeafSpec) -> str:
    if spec.slug:
        return spec.slug
    canonical = resolve_canonical_spec_for_name(spec.name)
    if canonical is not None:
        return canonical.canonical_slug
    return build_taxonomy_slug(spec.name)


def build_taxonomy_slug(value: str) -> str:
    transliterated = _transliterate(value)
    base = slugify(transliterated).strip("-")
    if not base:
        checksum = zlib.crc32(value.encode("utf-8")) & 0xFFFFFFFF
        base = f"category-{checksum:08x}"
    return base[:220]


def _transliterate(value: str) -> str:
    mapping = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "iu",
        "я": "ia",
        "і": "i",
        "ї": "i",
        "є": "ie",
        "ґ": "g",
    }
    chars: list[str] = []
    for char in value.lower():
        chars.append(mapping.get(char, char))
    return re.sub(r"\s+", " ", "".join(chars))
