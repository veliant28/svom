from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Iterable

from django.utils.text import slugify

from apps.catalog.models import Category


STATUS_ACTIVE = "active_mapping_candidate"
STATUS_REVIEW = "needs_review"
STATUS_IGNORE = "ignore"
STATUS_MISSING = "missing_leaf_category"
STATUS_CONFLICT = "conflict"


@dataclass(frozen=True)
class CategoryTarget:
    slug: str
    confidence: float
    reason: str
    desired_leaf_name: str = ""


@dataclass(frozen=True)
class CategoryDecision:
    status: str
    target_slug: str
    target_name: str
    root_name: str
    confidence: float
    reason: str
    desired_leaf_name: str = ""


def normalize_text(value: str) -> str:
    text = " ".join(str(value or "").split()).casefold()
    text = text.replace("ё", "е")
    return re.sub(r"[^0-9a-zа-яіїєґ\s/+.-]+", " ", text, flags=re.IGNORECASE)


def compact_text(value: str) -> str:
    return re.sub(r"[^0-9a-zа-яіїєґ]+", "", normalize_text(value), flags=re.IGNORECASE)


class GplCategoryMappingAuditor:
    def __init__(self) -> None:
        self.categories_by_slug = {
            category.slug: category
            for category in Category.objects.filter(is_active=True, is_assignable=True)
            .select_related("parent", "parent__parent")
            .only("id", "name", "slug", "parent_id", "parent__id", "parent__name", "parent__parent_id", "parent__parent__name", "is_assignable", "is_active")
        }
        self.alias_index = self._build_alias_index()
        self._exact_group_brand_map = self._build_exact_group_brand_map()

    def decide_group(self, *, rows: list[dict[str, str]]) -> CategoryDecision:
        if not rows:
            return CategoryDecision(status=STATUS_IGNORE, target_slug="", target_name="", root_name="", confidence=0.0, reason="empty_group")

        per_row: list[CategoryTarget] = []
        for row in rows:
            target = self.classify_row(row=row)
            if target is not None:
                per_row.append(target)

        if not per_row:
            suggestion = self._suggest_missing_leaf(rows=rows)
            if suggestion is not None:
                return CategoryDecision(
                    status=STATUS_MISSING,
                    target_slug="",
                    target_name="",
                    root_name=suggestion.root_name,
                    confidence=suggestion.confidence,
                    reason=suggestion.reason,
                    desired_leaf_name=suggestion.desired_leaf_name,
                )
            return CategoryDecision(status=STATUS_REVIEW, target_slug="", target_name="", root_name="", confidence=0.0, reason="no_confident_leaf_signal")

        slug_counts = Counter(item.slug for item in per_row)
        top_slug, top_count = slug_counts.most_common(1)[0]
        coverage = top_count / max(len(rows), 1)
        top_targets = [item for item in per_row if item.slug == top_slug]
        confidence = min(max(max(item.confidence for item in top_targets) * coverage, 0.0), 0.99)
        category = self.categories_by_slug.get(top_slug)
        if category is None:
            return CategoryDecision(
                status=STATUS_MISSING,
                target_slug=top_slug,
                target_name="",
                root_name="",
                confidence=confidence,
                reason="target_slug_missing",
                desired_leaf_name=top_targets[0].desired_leaf_name,
            )

        if len(slug_counts) > 1:
            second_count = slug_counts.most_common(2)[1][1]
            if second_count / max(len(rows), 1) >= 0.20 or coverage < 0.70:
                return CategoryDecision(
                    status=STATUS_CONFLICT,
                    target_slug=top_slug,
                    target_name=category.name,
                    root_name=self._root_name(category),
                    confidence=confidence,
                    reason=f"mixed_leaf_signals:{dict(slug_counts.most_common(5))}",
                )

        if coverage < 0.55:
            return CategoryDecision(
                status=STATUS_REVIEW,
                target_slug=top_slug,
                target_name=category.name,
                root_name=self._root_name(category),
                confidence=confidence,
                reason=f"low_group_coverage:{coverage:.2f}",
            )

        return CategoryDecision(
            status=STATUS_ACTIVE,
            target_slug=top_slug,
            target_name=category.name,
            root_name=self._root_name(category),
            confidence=confidence,
            reason=f"{top_targets[0].reason};group_coverage={coverage:.2f}",
        )

    def classify_row(self, *, row: dict[str, str]) -> CategoryTarget | None:
        raw_category = str(row.get("Категорія") or row.get("category") or "")
        raw_group = str(row.get("Група ТД") or row.get("group") or "")
        name = str(row.get("Найменування") or row.get("name") or row.get("title") or "")
        description = str(row.get("Опис") or row.get("description") or "")
        evidence = normalize_text(" ".join([raw_category, raw_group, name, description]))
        category_text = normalize_text(raw_category)
        group_text = normalize_text(raw_group)
        name_text = normalize_text(" ".join([name, description]))

        exact_group_brand = self._exact_group_brand_match(raw_category=raw_category, raw_group=raw_group)
        if exact_group_brand is not None:
            return exact_group_brand

        rule_target = self._rule_match(text=evidence, category_text=category_text, group_text=group_text, name_text=name_text)
        if rule_target is not None:
            return rule_target

        exact = self._exact_alias_match(category_text)
        if exact is not None:
            return exact

        return self._category_name_token_match(text=evidence)

    def _exact_alias_match(self, value: str) -> CategoryTarget | None:
        key = compact_text(value)
        if not key:
            return None
        slug = self.alias_index.get(key)
        if slug:
            return CategoryTarget(slug=slug, confidence=0.96, reason=f"exact_category_alias:{value}")
        return None

    def _rule_match(self, *, text: str, category_text: str, group_text: str, name_text: str) -> CategoryTarget | None:
        shock_accessory = self._shock_accessory_split_match(category_text=category_text, name_text=name_text)
        if shock_accessory is not None:
            return shock_accessory

        filter_or_tool = self._filter_tool_fluid_split_match(category_text=category_text, name_text=name_text, text=text)
        if filter_or_tool is not None:
            return filter_or_tool

        wiper_system = self._wiper_system_split_match(category_text=category_text, name_text=name_text)
        if wiper_system is not None:
            return wiper_system

        interior_care = self._interior_care_split_match(category_text=category_text, name_text=name_text)
        if interior_care is not None:
            return interior_care

        if any(token in category_text for token in ("резонатор", "резонатори", "резонаторы")):
            return CategoryTarget(slug="rezonator", confidence=0.96, reason="resonator_signal")
        if any(token in category_text for token in ("шини зимові", "зимние шины", "winter tires")):
            slug = self._first_existing_slug(("zimnie-shiny",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.98, reason="winter_tire_signal")
        if any(token in category_text for token in ("шини літні", "летние шины", "summer tires")):
            slug = self._first_existing_slug(("letnie-shiny",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.98, reason="summer_tire_signal")
        if any(token in category_text for token in ("шини всесезонні", "всесезонные шины", "all-season tires", "all season tires")):
            slug = self._first_existing_slug(("vsesezonnye-shiny",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.98, reason="all_season_tire_signal")
        if any(token in category_text for token in ("труби приймальні", "трубы приемные", "приемная труба", "приймальна труба")):
            return CategoryTarget(slug="priemnaia-truba", confidence=0.94, reason="front_exhaust_pipe_signal")
        if any(token in category_text for token in ("труби випускні", "трубы выпускные", "труби проміжні", "трубы промежуточные", "коліна", "колена")):
            return CategoryTarget(slug="truby-vykhlopnoi-sistemy", confidence=0.92, reason="exhaust_pipe_signal")
        if any(token in category_text for token in ("ароматизатор", "ароматизатори", "ароматизаторы")):
            return CategoryTarget(slug="aromatizatory", confidence=0.95, reason="air_freshener_signal")
        if self._contains_any(
            name_text,
            ("респіратор", "респиратор", "маска", "ffp", "respirator"),
        ):
            slug = self._first_existing_slug(("sredstva-zashchity-i-spetsodezhda",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.93, reason="ppe_respirator_split_signal")
        if (
            self._contains_any(" ".join((category_text, name_text)), ("spray paint",))
            or (
                self._contains_any(" ".join((category_text, name_text)), ("аерозол", "аэрозол"))
                and self._contains_any(" ".join((category_text, name_text)), ("фарб", "краск", "емал", "эмал", "paint"))
            )
        ):
            slug = self._first_existing_slug(("aerozolnye-kraski",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.95, reason="aerosol_paint_signal")
        if self._contains_any(category_text, ("поліролі кузова", "полироли кузова")):
            slug = self._first_existing_slug(("polirol-kuzova", "poliroli-kuzova"))
            if slug and self._contains_any(name_text, ("полірол", "полирол", "wax", "polish")):
                return CategoryTarget(slug=slug, confidence=0.93, reason="body_polish_split_signal")
            return None
        if self._contains_any(category_text, ("антикорозійні засоби та покриття", "антикоррозийные средства и покрытия")):
            slug = self._first_existing_slug(("antikorroziinye-sredstva-i-pokrytiia",))
            if slug and self._contains_any(name_text, ("антикор", "антикорроз", "покрыти", "coating", "антиграв", "пушсал", "консервац", "бітум", "битум", "мастик")):
                return CategoryTarget(slug=slug, confidence=0.92, reason="anticorrosion_split_signal")
            return None
        if self._contains_any(category_text, ("щітки та шкребки", "щетки и скребки")):
            slug = self._first_existing_slug(("shchetki-skrebki-i-vodosgony-dlia-avto",))
            if slug and self._contains_any(name_text, ("щітк", "щетк", "шкреб", "скреб", "водосгон")):
                return CategoryTarget(slug=slug, confidence=0.93, reason="brush_scraper_split_signal")
            return None
        if self._contains_any(category_text, ("побутова хімія", "бытовая химия")):
            slug = self._first_existing_slug(("bytovaia-khimiia", "bytovaia-himiia"))
            if slug and self._contains_any(name_text, ("очищ", "чистящ", "моющ", "мийн", "дезінф", "дезинф", "repellent", "комар", "кліщ")):
                return CategoryTarget(slug=slug, confidence=0.88, reason="household_chemicals_split_signal")
            return None
        if "шркш" in category_text:
            if self._contains_any(name_text, ("пильник", "пыльник", "cv boot", "boot")):
                slug = self._first_existing_slug(("pylnik-shrusa",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.92, reason="shrksh_cv_boot_split_signal")
            if self._contains_any(name_text, ("шрус", "cv joint", "шарнир", "тришип")):
                slug = self._first_existing_slug(("shrus",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.92, reason="shrksh_cv_joint_split_signal")
            slug = self._first_existing_slug(("shrus",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.86, reason="shrksh_default_cv_joint_signal")
            return None
        if self._contains_any(category_text, ("вкладиші", "вкладиши", "вкладыши")) or "вклад" in category_text:
            if self._contains_any(name_text, ("корін", "коренн")):
                slug = self._first_existing_slug(("vkladyshi-korennye",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.93, reason="main_bearing_split_signal")
            if self._contains_any(name_text, ("шатун",)):
                slug = self._first_existing_slug(("vkladyshi-shatunnye",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.93, reason="rod_bearing_split_signal")
            return None
        if self._contains_any(category_text, ("насоси паливні", "топливные насосы")):
            slug = self._first_existing_slug(("toplivnyi-nasos",))
            if slug and self._contains_any(name_text, ("паливн", "топливн", "fuel pump")):
                return CategoryTarget(slug=slug, confidence=0.95, reason="fuel_pump_split_signal")
            return None
        if self._contains_any(category_text, ("троси гальмівної системи", "тросы тормозной системы")) or ("трос" in category_text and ("гальм" in category_text or "тормоз" in category_text)):
            if self._contains_any(name_text, ("ручник", "ручного", "стояноч", "parking brake")):
                slug = self._first_existing_slug(("tros-ruchnika",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.94, reason="parking_brake_cable_split_signal")
            if self._contains_any(name_text, ("гальм", "тормоз", "brake cable")):
                slug = self._first_existing_slug(("trosy-tormoznoi-sistemy",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.88, reason="brake_cables_split_signal")
            return None
        if self._contains_any(category_text, ("троси автомобільні", "тросы автомобильные")):
            if self._contains_any(name_text, ("газ", "акселератор")):
                slug = self._first_existing_slug(("trosik-gaza",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.92, reason="throttle_cable_split_signal")
            if self._contains_any(name_text, ("зчеплен", "сцеплен")):
                slug = self._first_existing_slug(("trosik-stsepleniia",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.92, reason="clutch_cable_split_signal")
            if self._contains_any(name_text, ("спидометр",)):
                slug = self._first_existing_slug(("trosik-spidometra",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.92, reason="speedometer_cable_split_signal")
            if self._contains_any(name_text, ("замка двери",)):
                slug = self._first_existing_slug(("tros-zamka-dveri",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.90, reason="door_lock_cable_split_signal")
            return None
        if any(token in category_text for token in ("тяги та наконечники", "тяги и наконечники")):
            if self._contains_any(name_text, ("наконечник", "наконечники", "tie rod end")):
                return CategoryTarget(slug="rulevye-nakonechniki", confidence=0.92, reason="tie_rod_end_split_signal")
            if self._contains_any(name_text, ("тяга", "тяги", "steering rod", "axial joint")):
                return CategoryTarget(slug="rulevye-tiagi", confidence=0.90, reason="tie_rod_split_signal")
            return None
        if any(token in category_text for token in ("пильовики", "пыльники")):
            if self._contains_any(name_text, ("шрус", "cv boot", "шарнир")):
                return CategoryTarget(slug="pylnik-shrusa", confidence=0.93, reason="cv_boot_split_signal")
            if any(token in name_text for token in ("рулевой", "рульов", "тяга", "наконечник", "tie rod")):
                return CategoryTarget(slug="pylnik-rulevoi-tiagi", confidence=0.91, reason="steering_boot_split_signal")
            if any(token in name_text for token in ("амортиз", "стойк", "стійк", "shock")):
                return CategoryTarget(slug="pylniki-i-otboiniki-amortizatorov", confidence=0.90, reason="shock_boot_split_signal")
            return None
        if "датчик" in category_text or "датчики" in category_text:
            return self._sensor_split_match(text=text, category_text=category_text, group_text=group_text, name_text=name_text)
        if "проклад" in category_text:
            return self._gasket_split_match(text=text, name_text=name_text)
        if "підшип" in category_text or "подшип" in category_text:
            return self._bearing_split_match(text=text, name_text=name_text)
        if any(token in category_text for token in ("стабілізатор", "стабилизатор")):
            if self._contains_any(name_text, ("стойк", "стiйк", "стійк", "link stabilizer")):
                slug = self._first_existing_slug(("stoiki-stabilizatora",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.93, reason="stabilizer_link_split_signal")
            if self._contains_any(name_text, ("втулк", "bush")):
                slug = self._first_existing_slug(("vtulki-stabilizatora",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.91, reason="stabilizer_bushing_split_signal")
            return None
        if self._contains_any(category_text, ("подушки та опори двигуна", "подушки и опоры двигателя")):
            slug = self._first_existing_slug(("podushki-dvigatelia",))
            if slug and self._contains_any(name_text, ("опора двиг", "подушка двиг", "mount")):
                return CategoryTarget(slug=slug, confidence=0.92, reason="engine_mount_split_signal")
            return None
        if self._contains_any(category_text, ("циліндри гальмівної системи", "цилиндры тормозной системы")):
            if self._contains_any(name_text, ("головн", "главн")):
                slug = self._first_existing_slug(("glavnyi-tormoznoi-tsilindr",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.92, reason="brake_master_cylinder_split_signal")
            if self._contains_any(name_text, ("робоч", "рабоч", "wheel cylinder", "slave")):
                slug = self._first_existing_slug(("rabochii-tormoznoi-tsilindr",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.92, reason="brake_wheel_cylinder_split_signal")
            return None
        if "ремкомплект" in category_text or "ремкомплекти" in category_text:
            if self._contains_any(name_text, ("супорт", "суппорт")):
                slug = self._first_existing_slug(("remkomplekt-supporta",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.92, reason="caliper_repair_kit_split_signal")
            if self._contains_any(name_text, ("гальмівних колод", "тормозных колод")):
                slug = self._first_existing_slug(("remkomplekt-tormoznyh-kolodok",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.92, reason="brake_pad_repair_kit_split_signal")
            if self._contains_any(name_text, ("стояночного тормоза", "стояночного гальма")):
                slug = self._first_existing_slug(("remkomplekt-stoianochnogo-tormoza",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.91, reason="parking_brake_repair_kit_split_signal")
            if self._contains_any(name_text, ("зчепл", "сцепл")) and self._contains_any(name_text, ("циліндр", "цилиндр")):
                slug = self._first_existing_slug(("remkomplekt-tsilindra-stsepleniia",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.92, reason="clutch_cylinder_repair_kit_split_signal")
            if self._contains_any(name_text, ("турбин", "турбін")):
                slug = self._first_existing_slug(("remkomplekt-turbiny",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.90, reason="turbo_repair_kit_split_signal")
            if self._contains_any(name_text, ("стартер")):
                slug = self._first_existing_slug(("remkomplekt-startera",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.90, reason="starter_repair_kit_split_signal")
            return None
        if "ролики" in category_text or "ролик" in category_text:
            if self._contains_any(name_text, ("грм", "timing")):
                slug = self._first_existing_slug(("rolik-grm",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.91, reason="timing_roller_split_signal")
            if self._contains_any(name_text, ("натяж", "рем", "belt", "drive")):
                slug = self._first_existing_slug(("rolik-remnia-privodnogo",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.90, reason="drive_roller_split_signal")
            return None
        if "насоси" in category_text or "насосы" in category_text:
            if self._contains_any(name_text, ("водян", "помп", "water pump")):
                slug = self._first_existing_slug(("vodianoi-nasos",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.93, reason="water_pump_split_signal")
            if self._contains_any(name_text, ("маслян", "масляный")):
                slug = self._first_existing_slug(("maslianyi-nasos",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.91, reason="oil_pump_split_signal")
            if self._contains_any(name_text, ("гур", "гідропідсил", "гидроусил")):
                slug = self._first_existing_slug(("nasos-gidrousilitelia",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.90, reason="power_steering_pump_split_signal")
            if self._contains_any(name_text, ("бачка омывателя", "бачка омивача", "омыват")):
                slug = self._first_existing_slug(("nasos-bachka-omyvatelia",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.90, reason="washer_pump_split_signal")
            return None
        if self._contains_any(category_text, ("хомути", "хомуты", "стяжки", "затискачі", "зажимы")):
            slug = self._first_existing_slug(("homuty-stiazhki-i-zazhimy",))
            if slug and self._contains_any(name_text, ("хомут", "стяжк", "затискач", "зажим")):
                return CategoryTarget(slug=slug, confidence=0.92, reason="clamp_fastener_split_signal")
            return None
        if "рукавички" in category_text or "перчат" in category_text:
            slug = self._first_existing_slug(("sredstva-zashchity-i-spetsodezhda",))
            if slug and self._contains_any(name_text, ("рукавич", "перчат", "зварюв", "защит")):
                return CategoryTarget(slug=slug, confidence=0.93, reason="ppe_gloves_split_signal")
            return None
        if self._contains_any(category_text, ("серветки та губки", "салфетки и губки")):
            slug = self._first_existing_slug(("gubki-i-salfetki-dlia-avto",))
            if slug and self._contains_any(name_text, ("губк", "сервет", "салфет", "мікрофібр", "микрофибр")):
                return CategoryTarget(slug=slug, confidence=0.91, reason="car_sponges_wipes_split_signal")
            return None
        if "розчинники" in category_text or "растворители" in category_text:
            slug = self._first_existing_slug(("rastvoriteli-i-obezzhirivateli",))
            if slug and self._contains_any(name_text, ("розчинник", "раствор", "антисилик", "антисилік", "антісил", "знежир", "обезжир")):
                return CategoryTarget(slug=slug, confidence=0.90, reason="solvent_degreaser_split_signal")
            return None
        if "ключі" in category_text or "ключи" in category_text:
            slug = self._first_existing_slug(("golovki-tortsevye",))
            if slug and self._contains_any(name_text, ("головка торцева", "торцева головка", "головка", "socket")):
                return CategoryTarget(slug=slug, confidence=0.88, reason="socket_tool_split_signal")
            if self._contains_any(name_text, ("динамометр")):
                slug = self._first_existing_slug(("dinamometricheskie-kliuchi",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.88, reason="torque_wrench_split_signal")
            if self._contains_any(name_text, ("воротк",)):
                slug = self._first_existing_slug(("vorotki",))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.87, reason="breaker_bar_split_signal")
            if self._contains_any(name_text, ("ящик", "органайзер")):
                slug = self._first_existing_slug(("iashchik-dlia-instrumentov", "organaizery"))
                if slug:
                    return CategoryTarget(slug=slug, confidence=0.87, reason="tool_storage_split_signal")
            return None
        if any(token in category_text or token in name_text for token in ("фільтри олив", "фильтры масл", "оливний фільтр", "масляний фільтр", "масляный фильтр")):
            return CategoryTarget(slug="maslianyi-filtr", confidence=0.96, reason="oil_filter_signal")
        if any(token in category_text or token in name_text for token in ("свічки запалювання", "свечи зажигания", "свічка запалювання", "свеча зажигания")):
            return CategoryTarget(slug="svechi-zazhiganiia", confidence=0.96, reason="spark_plug_signal")
        if any(token in category_text or token in name_text for token in ("свічки накал", "свечи накал", "свічка накал", "свеча накал", "свічки розжар", "свечи накаливания")):
            return CategoryTarget(slug="svechi-nakala", confidence=0.96, reason="glow_plug_signal")
        if any(token in category_text or token in name_text for token in ("амортизатор", "амортизат")):
            return CategoryTarget(slug="amortizatory", confidence=0.95, reason="shock_absorber_signal")
        if any(token in category_text or token in name_text for token in ("кульов", "шарова опора", "шаровая опора", "ball joint")):
            return CategoryTarget(slug="sharovye-opory", confidence=0.94, reason="ball_joint_signal")
        if any(token in category_text or token in name_text for token in ("дроти запалювання", "дріт запалювання", "провода зажигания", "провод зажигания")):
            return CategoryTarget(slug="provoda-vysokovoltnye", confidence=0.93, reason="ignition_wire_signal")
        if any(token in category_text or token in name_text for token in ("шланги гальмів", "шланг гальмів", "шланги тормоз", "шланг тормоз")):
            return CategoryTarget(slug="tormoznoi-shlang", confidence=0.93, reason="brake_hose_signal")
        if any(token in category_text or token in name_text for token in ("ремін", "ремен", " belt")):
            if any(token in text for token in ("грм", "timing")):
                if any(token in text for token in ("комплект", "kit")):
                    return CategoryTarget(slug="komplekt-grm", confidence=0.95, reason="timing_kit_signal")
                return CategoryTarget(slug="remen-grm", confidence=0.94, reason="timing_belt_signal")
            return CategoryTarget(slug="remen-privodnoi", confidence=0.90, reason="drive_belt_signal")
        if any(token in category_text or token in name_text for token in ("очисники кузова", "очистители кузова", "очисник", "очиститель")):
            if "кондиц" in text:
                return CategoryTarget(slug="ochistiteli-konditsionera", confidence=0.90, reason="ac_cleaner_signal")
            return CategoryTarget(slug="uhod-za-avto", confidence=0.88, reason="car_care_cleaner_signal")

        checks: tuple[tuple[str, tuple[str, ...], float, str], ...] = (
            ("adblue-i-tehnicheskie-zhidkosti", ("adblue", "euroblue", "сечовин", "мочевин", "карбамід", "карбамид"), 0.98, "adblue_signal"),
            ("izolenta-i-elektromaterialy", ("ізоляційн", "изоляцион", "ізолент", "изолент"), 0.96, "insulation_tape_signal"),
            ("avtoemali-i-kraski", ("емал", "эмал", "фарб", "краск", "paint"), 0.93, "paint_signal"),
            ("antifriz", ("антифриз", "coolant", "тосол", "охолоджуюч", "охлаждающ"), 0.96, "coolant_signal"),
            ("zhidkost-tormoznaia", ("гальмівна рідина", "тормозная жидкость", "brake fluid", " dot "), 0.96, "brake_fluid_signal"),
            ("maslo-gur", (" гур", "гідропідсил", "гидроусил"), 0.92, "power_steering_oil_signal"),
            ("smazka", ("мастил", "смазк", "grease", "lubricant"), 0.88, "grease_signal"),
            ("maslianyi-filtr", ("масляний фільтр", "масляный фильтр", "фільтр масляний", "фильтр масляный", "фільтри олив", "фильтры масл", "oil filter"), 0.96, "oil_filter_signal"),
            ("vozdushnyi-filtr", ("повітряний фільтр", "воздушный фильтр", "фільтр повітряний", "фильтр воздушный", "повітряні фільтри", "воздушные фильтры", "air filter"), 0.96, "air_filter_signal"),
            ("filtr-salona", ("фільтр салону", "фильтр салона", "фільтри салону", "фильтры салона", "cabin filter", "pollen filter"), 0.96, "cabin_filter_signal"),
            ("toplivnyi-filtr", ("паливний фільтр", "топливный фильтр", "фільтр паливний", "фильтр топливный", "паливні фільтри", "топливные фильтры", "fuel filter"), 0.96, "fuel_filter_signal"),
            ("komplekt-filtrov", ("комплект фільтр", "комплект фильтр", "filter kit"), 0.93, "filter_kit_signal"),
            ("svechi-zazhiganiia", ("свічка запалювання", "свічки запалювання", "свеча зажигания", "свечи зажигания", "spark plug"), 0.96, "spark_plug_signal"),
            ("svechi-nakala", ("свічка накалу", "свічки накалу", "свеча накала", "свечи накала", "glow plug"), 0.96, "glow_plug_signal"),
            ("akkumuliatory", ("акумулятор", "аккумулятор", "battery"), 0.96, "battery_signal"),
            ("avtolampy", ("автоламп", "лампа", " bulb "), 0.90, "lamp_signal"),
            ("generator", ("генератор", "alternator"), 0.92, "alternator_signal"),
            ("starter", ("стартер", "starter"), 0.92, "starter_signal"),
            ("katushka-zazhiganiia", ("котушка запалювання", "катушка зажигания", "ignition coil"), 0.94, "ignition_coil_signal"),
            ("provoda-vysokovoltnye", ("провода высоковольт", "дроти високовольт", "дроти запалювання", "провода зажигания", "ignition wire", "ignition cable"), 0.92, "ignition_wire_signal"),
            ("tormoznye-kolodki", ("гальмівні колод", "тормозные колод", "brake pad"), 0.96, "brake_pad_signal"),
            ("tormoznye-diski", ("гальмівний диск", "тормозной диск", "brake disc", "brake rotor"), 0.96, "brake_disc_signal"),
            ("remkomplekt-supporta", ("ремкомплект супорт", "ремкомплект суппорт", "caliper repair"), 0.92, "caliper_repair_signal"),
            ("tormoznoi-support", ("супорт", "суппорт", "caliper"), 0.91, "caliper_signal"),
            ("tormoznoi-shlang", ("тормозной шланг", "гальмівний шланг", "тормозные шланги", "гальмівні шланги", "brake hose"), 0.92, "brake_hose_signal"),
            ("amortizatory", ("амортизатор", "shock absorber"), 0.95, "shock_absorber_signal"),
            ("sharovye-opory", ("кульова опора", "кульові опори", "шарова опора", "шаровая опора", "ball joint"), 0.94, "ball_joint_signal"),
            ("rychagi-i-tiagi", ("важіль", "рычаг", "control arm"), 0.90, "arm_signal"),
            ("sailentbloki", ("сайлентблок", "silentblock"), 0.90, "silentblock_signal"),
            ("stoiki-stabilizatora", ("стойка стаб", "стійка стаб", "stabilizer link"), 0.91, "stabilizer_link_signal"),
            ("vtulki-stabilizatora", ("втулка стаб", "bush stabilizer"), 0.91, "stabilizer_bushing_signal"),
            ("podshipnik-stupitsy", ("подшипник ступиц", "підшипник маточ", "wheel bearing"), 0.94, "wheel_bearing_signal"),
            ("stupitsa", ("ступиц", "маточин", "wheel hub"), 0.91, "hub_signal"),
            ("rulevye-nakonechniki", ("рульовий наконеч", "рулевой наконеч", "tie rod end"), 0.94, "tie_rod_end_signal"),
            ("rulevye-tiagi", ("рульова тяга", "рулевая тяга", "tie rod"), 0.92, "tie_rod_signal"),
            ("vodianoi-nasos", ("водяний насос", "водяной насос", "помпа", "water pump"), 0.95, "water_pump_signal"),
            ("termostat", ("термостат", "thermostat"), 0.95, "thermostat_signal"),
            ("radiator-ohlazhdeniia-dvigatelia", ("радіатор охолод", "радиатор охлажд", "cooling radiator"), 0.93, "cooling_radiator_signal"),
            ("remen-grm", ("ремінь грм", "ремень грм", "timing belt"), 0.95, "timing_belt_signal"),
            ("komplekt-grm", ("комплект грм", "timing kit"), 0.95, "timing_kit_signal"),
            ("remen-privodnoi", ("ремінь привод", "ремень привод", "drive belt"), 0.92, "drive_belt_signal"),
            ("rolik-remnia-privodnogo", ("ролик привод", "drive belt roller"), 0.90, "drive_roller_signal"),
            ("glushitel", ("глушник", "глушитель", "muffler"), 0.95, "muffler_signal"),
            ("rezonator", ("резонатор", "resonator"), 0.96, "resonator_signal"),
            ("priemnaia-truba", ("приймальна труба", "приемная труба", "front exhaust pipe"), 0.94, "front_exhaust_pipe_signal"),
            ("truby-vykhlopnoi-sistemy", ("випускна труба", "выпускная труба", "проміжна труба", "промежуточная труба", "exhaust pipe"), 0.92, "exhaust_pipe_signal"),
            ("gofra-vyhlopnoi-sistemy", ("гофра", "exhaust flex"), 0.92, "exhaust_flex_signal"),
            ("prokladka-glushitelia", ("прокладка глуш", "gasket exhaust"), 0.90, "exhaust_gasket_signal"),
            ("komplekt-stsepleniia", ("комплект зчеп", "комплект сцеп", "clutch kit"), 0.94, "clutch_kit_signal"),
            ("disk-stsepleniia", ("диск зчеп", "диск сцеп", "clutch disc"), 0.92, "clutch_disc_signal"),
            ("shrus", ("шрус", "cv joint"), 0.94, "cv_joint_signal"),
            ("pylnik-shrusa", ("пильник шрус", "пыльник шрус", "cv boot"), 0.93, "cv_boot_signal"),
            ("dvorniki", ("двірник", "дворник", "щітка скло", "щетка стекл", "wiper blade"), 0.92, "wiper_signal"),
            ("aromatizatory", ("ароматизатор", "air freshener"), 0.95, "air_freshener_signal"),
            ("aptechki-i-bezopasnost", ("аптечк", "first aid"), 0.90, "first_aid_signal"),
            ("ognetushiteli", ("вогнегас", "огнетуш", "fire extinguisher"), 0.90, "fire_extinguisher_signal"),
            ("domkraty", ("домкрат", "jack"), 0.90, "jack_signal"),
        )

        for slug, tokens, confidence, reason in checks:
            if slug not in self.categories_by_slug:
                continue
            if any(token in text for token in tokens) or any(token in category_text for token in tokens) or any(token in name_text for token in tokens):
                return CategoryTarget(slug=slug, confidence=confidence, reason=reason)
        return None

    def _wiper_system_split_match(self, *, category_text: str, name_text: str) -> CategoryTarget | None:
        combined = " ".join((category_text, name_text))
        if not self._contains_any(
            combined,
            (
                "склоочис",
                "стеклоочис",
                "двірник",
                "дворник",
                "wiper",
            ),
        ):
            return None

        if self._contains_any(combined, ("перемикач", "переключател", "switch")):
            slug = self._first_existing_slug(("podrulevye-perekliuchateli",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.94, reason="wiper_switch_split_signal")

        if self._contains_any(combined, ("трапец", "механізм", "механизм", "linkage")):
            slug = self._first_existing_slug(("trapetsiia-stekloochistitelia",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.95, reason="wiper_linkage_split_signal")

        if self._contains_any(combined, ("поводок", "щіткотримач", "щеткодерж", "arm")):
            slug = self._first_existing_slug(("povodok-stekloochistitelia",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.94, reason="wiper_arm_split_signal")

        if self._contains_any(combined, ("форсунк", "жиклер", "washer nozzle")):
            slug = self._first_existing_slug(("forsunki-omyvatelia-stekla",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.94, reason="washer_nozzle_split_signal")

        if self._contains_any(category_text, ("щітки склоочисників", "щетки стеклоочистителей", "щітка склоочисника", "щетка стеклоочистителя")):
            slug = self._first_existing_slug(("dvorniki",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.96, reason="wiper_blade_category_signal")

        if self._contains_any(combined, ("щітк", "щетк", "резинка", "blade")):
            slug = self._first_existing_slug(("dvorniki",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.93, reason="wiper_blade_split_signal")

        return None

    def _interior_care_split_match(self, *, category_text: str, name_text: str) -> CategoryTarget | None:
        if not self._contains_any(category_text, ("поліролі торпедо", "полироли торпедо")):
            return None
        if self._contains_any(name_text, ("полірол", "полирол", "пластик", "торпед", "cockpit", "dashboard")):
            slug = self._first_existing_slug(("uhod-za-avto",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.92, reason="interior_plastic_care_signal")
        return None

    def _shock_accessory_split_match(self, *, category_text: str, name_text: str) -> CategoryTarget | None:
        combined = " ".join((category_text, name_text))
        if not self._contains_any(combined, ("амортиз", "стойк", "стійк", "shock", "strut")):
            return None

        if self._contains_any(combined, ("відбій", "отбой", "bump stop")):
            slug = self._first_existing_slug(("pylniki-i-otboiniki-amortizatorov",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.96, reason="shock_bump_stop_split_signal")

        if self._contains_any(combined, ("пильник", "пыльник", "dust boot", "shock boot", "strut boot")):
            slug = self._first_existing_slug(("pylniki-i-otboiniki-amortizatorov",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.95, reason="shock_boot_split_signal")

        if self._contains_any(name_text, ("підшипник опори", "подшипник опоры", "опорний підшипник", "опорный подшипник")):
            slug = self._first_existing_slug(("opornyi-podshipnik",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.95, reason="shock_support_bearing_split_signal")

        if self._contains_any(combined, ("опора амортиз", "опори амортиз", "опора стойк", "опора стійк", "strut mount", "shock mount")):
            slug = self._first_existing_slug(("opora-amortizatora",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.96, reason="shock_mount_split_signal")

        if self._contains_any(name_text, ("сайлентблок амортиз", "silentblock shock", "shock bushing")):
            slug = self._first_existing_slug(("sailentblok-amortizatora", "sailentbloki"))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.93, reason="shock_silentblock_split_signal")

        return None

    def _filter_tool_fluid_split_match(self, *, category_text: str, name_text: str, text: str) -> CategoryTarget | None:
        combined = " ".join((category_text, name_text, text))

        if self._contains_any(combined, ("домкрат", "jack")):
            slug = self._first_existing_slug(("domkraty",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.96, reason="jack_split_signal")

        if self._contains_any(combined, ("фільтр акпп", "фильтр акпп", "filter atf", "transmission filter")):
            slug = self._first_existing_slug(("maslianyi-filtr-akpp",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.95, reason="atf_filter_split_signal")

        if self._contains_any(combined, ("фільтр", "фильтр", "filter")) and self._contains_any(
            combined,
            ("гідравл", "гидравл", "hydraulic"),
        ):
            slug = self._first_existing_slug(("maslianyi-filtr",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.92, reason="hydraulic_filter_split_signal")

        if self._contains_any(category_text, ("спеціалізовані фільтри", "специализированные фильтры")) and self._contains_any(
            name_text,
            ("фільтр", "фильтр", "filter"),
        ):
            slug = self._first_existing_slug(("maslianyi-filtr",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.91, reason="specialized_filter_fallback_signal")

        if self._contains_any(category_text, ("присадки", "добавки")) or self._contains_any(name_text, ("присадка", "additive", "treatment")):
            slug = self._first_existing_slug(("prisadki",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.92, reason="additive_split_signal")

        oil_context = self._contains_any(combined, ("олива", "масло", "oil", "fluid", "рідина", "жидкость"))
        transmission_signal = self._contains_any(
            combined,
            ("трансміс", "трансмис", " atf", "dexron", "gl-4", "gl4", "gl-5", "gl5", "75w", "80w", "gear oil"),
        )
        if oil_context and transmission_signal:
            slug = self._first_existing_slug(("maslo-transmissionnoe",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.94, reason="transmission_oil_signal")

        engine_oil_signal = self._contains_any(combined, ("моторна олива", "моторное масло", "engine oil", "motor oil"))
        viscosity_signal = self._contains_any(combined, (" 0w", " 5w", " 10w", " 15w", " 20w"))
        if engine_oil_signal or (oil_context and viscosity_signal and not transmission_signal):
            slug = self._first_existing_slug(("motornoe-maslo",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.94, reason="engine_oil_signal")

        hydraulic_signal = self._contains_any(combined, ("гідравл", "гидравл", "hydraulic", "hlp", "l-hm", "l-hv", "iso vg"))
        if hydraulic_signal and oil_context:
            slug = self._first_existing_slug(("gidravlicheskoe-maslo", "gidravlicheskie-masla"))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.92, reason="hydraulic_oil_signal")

        return None

    def _sensor_split_match(self, *, text: str, category_text: str, group_text: str, name_text: str) -> CategoryTarget | None:
        # Keep broad sensor groups in review by default and allow only precise leaf matches.
        combined = " ".join((text, category_text, group_text, name_text))
        if "abs" in combined:
            slug = self._first_existing_slug(("datchik-abs",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.95, reason="sensor_abs_split_signal")
        if any(token in combined for token in ("температур", "охлажда", "охолоджуюч", "coolant")):
            slug = self._first_existing_slug((
                "datchik-temperatury-okhlazhdaiushchei-zhidkosti",
                "datchik-temperatury-ohlazhdayushchei-zhidkosti",
            ))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.92, reason="sensor_coolant_temperature_split_signal")
        if any(token in combined for token in ("выхлоп", "випуск", "відпрацьован", "отработан")):
            slug = self._first_existing_slug(("datchik-davleniia-vyhlopnyh-gazov",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.91, reason="sensor_exhaust_pressure_split_signal")
        if any(token in combined for token in ("наддув", "boost", "map", "коллектор", "турбин")):
            slug = self._first_existing_slug(("datchik-davleniia-nadduva-turbiny",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.91, reason="sensor_boost_pressure_split_signal")
        if any(token in combined for token in ("давлен", "тиск")):
            slug = self._first_existing_slug((
                "datchik-davleniia-nadduva-turbiny",
                "datchik-davleniia-vyhlopnyh-gazov",
            ))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.86, reason="sensor_pressure_split_signal")
        if any(token in combined for token in ("стоп сигнал", "стоп-сигнал")):
            slug = self._first_existing_slug(("datchik-stop-signala",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.90, reason="sensor_stop_signal_split_signal")
        if any(token in combined for token in ("парктро",)):
            slug = self._first_existing_slug(("datchik-parktronika",))
            if slug:
                return CategoryTarget(slug=slug, confidence=0.90, reason="sensor_parktronic_split_signal")
        return None

    def _gasket_split_match(self, *, text: str, name_text: str) -> CategoryTarget | None:
        combined = " ".join((text, name_text))
        checks: tuple[tuple[str, bool, float, str], ...] = (
            ("prokladka-gbts", ("гбц" in combined or "головк" in combined), 0.95, "gasket_head_signal"),
            ("prokladka-klapannoi-kryshki", ("клапан" in combined and "крышк" in combined), 0.94, "gasket_valve_cover_signal"),
            ("prokladka-vpusknogo-kollektora", ("впускн" in combined and "коллектор" in combined), 0.93, "gasket_intake_manifold_signal"),
            ("prokladka-teploobmennika", ("теплообмен" in combined), 0.92, "gasket_heat_exchanger_signal"),
            ("prokladka-maslianogo-nasosa", ("масляного насоса" in combined or "масляного насос" in combined), 0.92, "gasket_oil_pump_signal"),
            ("prokladka-glushitelia", ("глуш" in combined or "выхлоп" in combined or "випуск" in combined), 0.93, "gasket_exhaust_signal"),
            ("prokladka-poddona", ("поддон" in combined), 0.94, "gasket_oil_pan_signal"),
            ("prokladka-korpusa-maslianogo-filtra", ("корпус" in combined and "маслян" in combined and "фильтр" in combined), 0.92, "gasket_oil_filter_housing_signal"),
            ("komplekt-prokladok-gbts", ("комплект" in combined and "гбц" in combined), 0.93, "gasket_head_set_signal"),
            ("komplekt-prokladok-dvigatelia", ("комплект" in combined and ("двиг" in combined or "мотор" in combined)), 0.92, "gasket_engine_set_signal"),
        )
        for slug, matched, confidence, reason in checks:
            if slug not in self.categories_by_slug or not matched:
                continue
            return CategoryTarget(slug=slug, confidence=confidence, reason=reason)
        return None

    def _bearing_split_match(self, *, text: str, name_text: str) -> CategoryTarget | None:
        combined = " ".join((text, name_text))
        checks: tuple[tuple[str, bool, float, str], ...] = (
            ("podshipnik-stupitsy", ("ступиц" in combined or "маточин" in combined), 0.93, "bearing_hub_signal"),
            ("opornyi-podshipnik", ("опорн" in combined), 0.91, "bearing_support_signal"),
            ("podshipnik-kpp", ("кпп" in combined), 0.90, "bearing_gearbox_signal"),
            ("podshipnik-reduktora", ("редуктор" in combined), 0.90, "bearing_differential_signal"),
        )
        for slug, matched, confidence, reason in checks:
            if slug not in self.categories_by_slug or not matched:
                continue
            return CategoryTarget(slug=slug, confidence=confidence, reason=reason)
        return None

    def _exact_group_brand_match(self, *, raw_category: str, raw_group: str) -> CategoryTarget | None:
        category_key = compact_text(raw_category)
        group_key = compact_text(raw_group)
        if not category_key or not group_key:
            return None
        slug = self._exact_group_brand_map.get((category_key, group_key))
        if not slug or slug not in self.categories_by_slug:
            return None
        return CategoryTarget(slug=slug, confidence=0.99, reason=f"confirmed_group_brand_mapping:{raw_category}|{raw_group}")

    def _build_exact_group_brand_map(self) -> dict[tuple[str, str], str]:
        pairs: tuple[tuple[str, str, str], ...] = (
            ("Резонатори", "POLMO", "rezonator"),
            ("Труби приймальні", "POLMO", "priemnaia-truba"),
            ("Труби випускні, проміжні, коліна", "POLMO", "truby-vykhlopnoi-sistemy"),
            ("Ароматизатори", "K2", "aromatizatory"),
            ("Резонатори", "ТМК", "rezonator"),
            ("Резонатори", "BOSAL", "rezonator"),
            ("Ароматизатори", "LITTLE TREES", "aromatizatory"),
        )
        out: dict[tuple[str, str], str] = {}
        for raw_category, raw_group, slug in pairs:
            if slug not in self.categories_by_slug:
                continue
            out[(compact_text(raw_category), compact_text(raw_group))] = slug
        return out

    def _first_existing_slug(self, candidates: tuple[str, ...]) -> str:
        for slug in candidates:
            if slug in self.categories_by_slug:
                return slug
        return ""

    @staticmethod
    def _contains_any(value: str, tokens: tuple[str, ...]) -> bool:
        text = str(value or "")
        return any(token in text for token in tokens)

    def _category_name_token_match(self, *, text: str) -> CategoryTarget | None:
        best_slug = ""
        best_score = 0
        for category in self.categories_by_slug.values():
            tokens = [token for token in normalize_text(category.name).split() if len(token) >= 5]
            if not tokens:
                continue
            score = sum(1 for token in tokens if token in text)
            if score > best_score:
                best_score = score
                best_slug = category.slug
        if best_slug and best_score >= 2:
            return CategoryTarget(slug=best_slug, confidence=0.82, reason="category_name_token_match")
        return None

    def _suggest_missing_leaf(self, *, rows: list[dict[str, str]]) -> CategoryDecision | None:
        raw_categories = Counter(str(row.get("Категорія") or "").strip() for row in rows if str(row.get("Категорія") or "").strip())
        if not raw_categories:
            return None
        name, count = raw_categories.most_common(1)[0]
        if count < 3:
            return None
        evidence = normalize_text(" ".join(str(row.get("Найменування") or "") for row in rows[:15]))
        root_name = self._suggest_root_name(evidence=evidence, raw_category=name)
        return CategoryDecision(
            status=STATUS_MISSING,
            target_slug="",
            target_name="",
            root_name=root_name,
            confidence=0.55,
            reason="no_existing_leaf_for_repeated_raw_category",
            desired_leaf_name=name,
        )

    def _suggest_root_name(self, *, evidence: str, raw_category: str) -> str:
        text = f"{normalize_text(raw_category)} {evidence}"
        if any(token in text for token in ("торм", "гальм", "brake")):
            return "Тормозная система"
        if any(token in text for token in ("амортиз", "рулев", "рульов", "подвес", "підвіс", "ступиц", "сайлент")):
            return "Подвеска и рулевое"
        if any(token in text for token in ("фільтр", "фильтр", "грм", "свіч", "свеч", "масл", "олив")):
            return "Запчасти для ТО"
        if any(token in text for token in ("емал", "краск", "фарб", "adblue", "антифриз", "олив", "масл")):
            return "Автохимия и аксессуары"
        if any(token in text for token in ("ламп", "фара", "генератор", "стартер", "акум", "аккум", "датчик")):
            return "Электрика и освещение"
        if any(token in text for token in ("кузов", "бампер", "дзерк", "зерк", "двер", "щіт", "щет")):
            return "Детали кузова"
        if any(token in text for token in ("термостат", "радиатор", "помпа", "охолод", "охлаж")):
            return "Охлаждение и отопление"
        return "needs_manual_root_choice"

    def _build_alias_index(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        manual_aliases = {
            "adblue": "adblue-i-tehnicheskie-zhidkosti",
            "ізоляційні стрічки": "izolenta-i-elektromaterialy",
            "изоляционные ленты": "izolenta-i-elektromaterialy",
            "автоемалі": "avtoemali-i-kraski",
            "автоэмали": "avtoemali-i-kraski",
            "акумулятори": "akkumuliatory",
            "аккумуляторы": "akkumuliatory",
            "двірники": "dvorniki",
            "дворники": "dvorniki",
            "аптечки": "aptechki-i-bezopasnost",
        }
        for raw, slug in manual_aliases.items():
            if slug in self.categories_by_slug:
                aliases[compact_text(raw)] = slug
        for category in self.categories_by_slug.values():
            values = (category.name, category.name_uk, category.name_ru, category.name_en, category.slug.replace("-", " "))
            for value in values:
                key = compact_text(value)
                if key and key not in aliases:
                    aliases[key] = category.slug
        return aliases

    @staticmethod
    def _root_name(category: Category) -> str:
        current = category
        while current.parent_id and current.parent is not None:
            current = current.parent
        return current.name


def build_suggested_slug(name: str) -> str:
    return slugify(str(name or "").strip())[:220] or "missing-category"


def priority_for_count(count: int) -> str:
    if count >= 100:
        return "high"
    if count >= 25:
        return "medium"
    return "low"


def join_examples(values: Iterable[str], *, limit: int) -> str:
    out: list[str] = []
    for value in values:
        text = " ".join(str(value or "").split())
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return " | ".join(out)
