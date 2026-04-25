import type {
  BackofficeHeroBlockEffect,
  BackofficeHeroBlockSettings,
  BackofficeHeroSlide,
} from "@/features/backoffice/types/hero-block.types";
import {
  HERO_BLOCK_UPDATED_AT_KEY,
  HERO_BLOCK_UPDATED_EVENT,
} from "@/shared/lib/hero-block-sync";

export type SettingsForm = {
  autoplay_enabled: boolean;
  transition_effect: BackofficeHeroBlockEffect;
  transition_interval_seconds: number;
  transition_speed_ms: number;
  max_active_slides: number;
};

export type SlideForm = {
  title_uk: string;
  title_ru: string;
  title_en: string;
  subtitle_uk: string;
  subtitle_ru: string;
  subtitle_en: string;
  cta_url: string;
  sort_order: number;
  is_active: boolean;
  desktop_image_file: File | null;
  mobile_image_file: File | null;
};

export const DEFAULT_SETTINGS_FORM: SettingsForm = {
  autoplay_enabled: true,
  transition_effect: "crossfade",
  transition_interval_seconds: 5,
  transition_speed_ms: 900,
  max_active_slides: 10,
};

export const DEFAULT_SLIDE_FORM: SlideForm = {
  title_uk: "",
  title_ru: "",
  title_en: "",
  subtitle_uk: "",
  subtitle_ru: "",
  subtitle_en: "",
  cta_url: "/catalog",
  sort_order: 1,
  is_active: true,
  desktop_image_file: null,
  mobile_image_file: null,
};

export function clampNumber(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.max(min, Math.min(max, value));
}

export function sortSlides(items: BackofficeHeroSlide[]): BackofficeHeroSlide[] {
  return [...items].sort((left, right) => left.sort_order - right.sort_order);
}

export function toSettingsForm(value: BackofficeHeroBlockSettings): SettingsForm {
  return {
    autoplay_enabled: Boolean(value.autoplay_enabled),
    transition_effect: value.transition_effect,
    transition_interval_seconds: Math.max(1, Math.round(Number(value.transition_interval_ms || 5000) / 1000)),
    transition_speed_ms: clampNumber(Number(value.transition_speed_ms || 900), 150, 10000),
    max_active_slides: clampNumber(Number(value.max_active_slides || 10), 1, 10),
  };
}

export function toSlideForm(item: BackofficeHeroSlide): SlideForm {
  return {
    title_uk: item.title_uk || "",
    title_ru: item.title_ru || "",
    title_en: item.title_en || "",
    subtitle_uk: item.subtitle_uk || "",
    subtitle_ru: item.subtitle_ru || "",
    subtitle_en: item.subtitle_en || "",
    cta_url: item.cta_url || "",
    sort_order: Number(item.sort_order || 1),
    is_active: Boolean(item.is_active),
    desktop_image_file: null,
    mobile_image_file: null,
  };
}

export function emitHeroBlockUpdated(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(HERO_BLOCK_UPDATED_AT_KEY, String(Date.now()));
  window.dispatchEvent(new CustomEvent(HERO_BLOCK_UPDATED_EVENT));
}

export function hasTitle(form: SlideForm): boolean {
  return Boolean(form.title_uk.trim() || form.title_ru.trim() || form.title_en.trim());
}
