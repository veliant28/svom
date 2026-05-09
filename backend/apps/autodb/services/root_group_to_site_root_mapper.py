from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SiteRootSpec:
    slug: str
    name: str


@dataclass(frozen=True)
class RootGroupMappingResult:
    status: str
    site_root_slug: str
    site_root_name: str
    confidence: float
    reason: str


class AutoDbRootGroupToSiteRootMapper:
    STATUS_MAPPED = "mapped"
    STATUS_NEEDS_REVIEW = "needs_review"
    STATUS_SKIPPED_NO_ROOT_MAPPING = "skipped_no_root_mapping"

    SITE_ROOTS: tuple[SiteRootSpec, ...] = (
        SiteRootSpec(slug="to-i-raskhodniki", name="ТО и расходники"),
        SiteRootSpec(slug="avtokhimiia-i-aksesuary", name="Автохимия и аксессуары"),
        SiteRootSpec(slug="tormoznaia-sistema", name="Тормозная система"),
        SiteRootSpec(slug="dvigatel-i-vykhlop", name="Двигатель и выхлоп"),
        SiteRootSpec(slug="podveska-i-rulevoe", name="Подвеска и рулевое"),
        SiteRootSpec(slug="stseplenie-i-transmissiia", name="Сцепление и трансмиссия"),
        SiteRootSpec(slug="elektrika-i-osveshchenie", name="Электрика и освещение"),
        SiteRootSpec(slug="kuzov-i-salon", name="Кузов и салон"),
        SiteRootSpec(slug="kolesa-i-shiny", name="Колёса и шины"),
        SiteRootSpec(slug="klimat-komfort-i-bezopasnost", name="Климат, комфорт и безопасность"),
    )

    GROUP_MAP: dict[str, str] = {
        "Детали для сервиса / ТО / ухода": "to-i-raskhodniki",
        "фильтр": "to-i-raskhodniki",
        "тормозная система": "tormoznaia-sistema",
        "Двигатель": "dvigatel-i-vykhlop",
        "Подготовка топливной смеси": "dvigatel-i-vykhlop",
        "Система выпуска": "dvigatel-i-vykhlop",
        "Система охлаждения": "dvigatel-i-vykhlop",
        "Система подачи топлива": "dvigatel-i-vykhlop",
        "Гибрид": "dvigatel-i-vykhlop",
        "Подвеска / амортизация": "podveska-i-rulevoe",
        "Подвеска оси / система подвески / колеса": "podveska-i-rulevoe",
        "Рулевое управления": "podveska-i-rulevoe",
        "Пневматическая система": "podveska-i-rulevoe",
        "Система сцепления / навесные части": "stseplenie-i-transmissiia",
        "Коробка передач": "stseplenie-i-transmissiia",
        "Главная передача": "stseplenie-i-transmissiia",
        "Вспомогательная / рабочая передача": "stseplenie-i-transmissiia",
        "Привод колеса": "stseplenie-i-transmissiia",
        "Электрика": "elektrika-i-osveshchenie",
        "Электропривод": "elektrika-i-osveshchenie",
        "Информационная / коммуникационная система": "elektrika-i-osveshchenie",
        "Кузов": "kuzov-i-salon",
        "Внутренняя отделка": "kuzov-i-salon",
        "Замок": "kuzov-i-salon",
        "Система очистки окон": "kuzov-i-salon",
        "Система очистки фар": "kuzov-i-salon",
        "Колёса / шины": "kolesa-i-shiny",
        "Кондиционер": "klimat-komfort-i-bezopasnost",
        "Отопление / вентиляция": "klimat-komfort-i-bezopasnost",
        "Дополнительные удобства": "klimat-komfort-i-bezopasnost",
        "Система безопасности": "klimat-komfort-i-bezopasnost",
        "Химические продукты": "avtokhimiia-i-aksesuary",
        "Оборудование для перевозки": "avtokhimiia-i-aksesuary",
        "Прицепное оборудование / комплектующие": "avtokhimiia-i-aksesuary",
    }

    _MAINTENANCE_KEYWORDS = (
        "свеча зажиган",
        "свеча накал",
        "spark plug",
        "glow plug",
        "фильтр",
        "фільтр",
        "filter",
        "ремень",
        "ролик",
        "грм",
        "масло",
        "oil",
        "то",
        "service",
    )
    _ELECTRICS_KEYWORDS = (
        "катуш",
        "модул",
        "провод",
        "реле",
        "датчик",
        "блок управл",
        "ignition coil",
        "ignition module",
        "cable",
    )
    _ACCESSORY_KEYWORDS = (
        "инструмент",
        "аксесс",
        "аксесу",
        "крепеж",
        "кріпл",
        "универсал",
        "набор",
    )
    _BRAKE_KEYWORDS = ("тормоз", "гальм", "brake", "колодк", "суппорт")
    _BODY_KEYWORDS = ("кузов", "салон", "бампер", "двер", "скло", "стекл", "зеркал", "дзеркал")

    KEYWORD_RULES: tuple[tuple[str, tuple[str, ...], float], ...] = (
        ("to-i-raskhodniki", ("фильтр", "filter", "масло", "oil", "свеч", "ремень", "ролик", "грм", "то", "расход"), 0.82),
        ("avtokhimiia-i-aksesuary", ("автохим", "очист", "присад", "эмаль", "краск", "смаз", "аксесс", "інструмент", "инструмент"), 0.78),
        ("dvigatel-i-vykhlop", ("двиг", "мотор", "выхлоп", "випуск", "глуш", "охлаж", "помпа", "топлив", "инжектор"), 0.8),
        ("elektrika-i-osveshchenie", ("датчик", "ламп", "фара", "генератор", "стартер", "катуш", "реле", "провод", "электр"), 0.8),
    )

    def __init__(self):
        self._site_root_by_slug = {item.slug: item for item in self.SITE_ROOTS}

    def map_group(self, *, root_group: str, sample_text: str = "") -> RootGroupMappingResult:
        return self.map_prd(
            root_group=root_group,
            prd_description=sample_text,
            prd_normalized_description="",
            prd_assembly_group_description=root_group,
            prd_usage_description="",
            article_title="",
        )

    def map_prd(
        self,
        *,
        root_group: str,
        prd_description: str,
        prd_normalized_description: str,
        prd_assembly_group_description: str,
        prd_usage_description: str,
        article_title: str = "",
    ) -> RootGroupMappingResult:
        group = str(root_group or "").strip()
        if not group:
            return RootGroupMappingResult(
                status=self.STATUS_SKIPPED_NO_ROOT_MAPPING,
                site_root_slug="",
                site_root_name="",
                confidence=0.0,
                reason="empty_group",
            )

        haystack = self._normalize_haystack(
            [
                group,
                prd_description,
                prd_normalized_description,
                prd_assembly_group_description,
                prd_usage_description,
                article_title,
            ]
        )
        if group == "Система зажигания / накаливания":
            return self._map_ignition_group(haystack=haystack)
        if group == "Комплектующие":
            return self._map_components_group(haystack=haystack)

        mapped_slug = self.GROUP_MAP.get(group)
        if mapped_slug:
            spec = self._site_root_by_slug[mapped_slug]
            return RootGroupMappingResult(
                status=self.STATUS_MAPPED,
                site_root_slug=spec.slug,
                site_root_name=spec.name,
                confidence=0.97,
                reason=f"group_map:{group}",
            )

        for slug, keywords, confidence in self.KEYWORD_RULES:
            for keyword in keywords:
                if keyword in haystack:
                    spec = self._site_root_by_slug[slug]
                    return RootGroupMappingResult(
                        status=self.STATUS_MAPPED,
                        site_root_slug=spec.slug,
                        site_root_name=spec.name,
                        confidence=confidence,
                        reason=f"keyword:{keyword}",
                    )

        return RootGroupMappingResult(
            status=self.STATUS_SKIPPED_NO_ROOT_MAPPING,
            site_root_slug="",
            site_root_name="",
            confidence=0.0,
            reason="no_rule_match",
        )

    def _map_ignition_group(self, *, haystack: str) -> RootGroupMappingResult:
        if self._contains_any(haystack, self._ELECTRICS_KEYWORDS):
            return self._mapped(slug="elektrika-i-osveshchenie", confidence=0.91, reason="ignition_context:electrics")
        if self._contains_any(haystack, self._MAINTENANCE_KEYWORDS):
            return self._mapped(slug="to-i-raskhodniki", confidence=0.93, reason="ignition_context:service_parts")
        return RootGroupMappingResult(
            status=self.STATUS_NEEDS_REVIEW,
            site_root_slug="",
            site_root_name="",
            confidence=0.0,
            reason="ignition_context:unclear",
        )

    def _map_components_group(self, *, haystack: str) -> RootGroupMappingResult:
        if self._contains_any(haystack, self._MAINTENANCE_KEYWORDS):
            return self._mapped(slug="to-i-raskhodniki", confidence=0.9, reason="components_context:service_parts")
        if self._contains_any(haystack, self._BRAKE_KEYWORDS):
            return self._mapped(slug="tormoznaia-sistema", confidence=0.89, reason="components_context:brake")
        if self._contains_any(haystack, self._BODY_KEYWORDS):
            return self._mapped(slug="kuzov-i-salon", confidence=0.88, reason="components_context:body")
        if self._contains_any(haystack, self._ELECTRICS_KEYWORDS):
            return self._mapped(slug="elektrika-i-osveshchenie", confidence=0.88, reason="components_context:electrics")
        if self._contains_any(haystack, self._ACCESSORY_KEYWORDS):
            return self._mapped(slug="avtokhimiia-i-aksesuary", confidence=0.8, reason="components_context:accessory")
        return RootGroupMappingResult(
            status=self.STATUS_NEEDS_REVIEW,
            site_root_slug="",
            site_root_name="",
            confidence=0.0,
            reason="components_context:unclear",
        )

    def _mapped(self, *, slug: str, confidence: float, reason: str) -> RootGroupMappingResult:
        spec = self._site_root_by_slug[slug]
        return RootGroupMappingResult(
            status=self.STATUS_MAPPED,
            site_root_slug=spec.slug,
            site_root_name=spec.name,
            confidence=confidence,
            reason=reason,
        )

    @staticmethod
    def _normalize_haystack(parts: list[str]) -> str:
        text = " ".join(str(item or "") for item in parts).casefold()
        text = re.sub(r"[^0-9a-zа-яіїєґ\s-]+", " ", text, flags=re.IGNORECASE)
        return " ".join(text.split())

    @staticmethod
    def _contains_any(haystack: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in haystack for keyword in keywords)
