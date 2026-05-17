export type LocalizedProductNameSource = {
  name?: string | null;
  display_name?: string | null;
  name_uk?: string | null;
  name_ru?: string | null;
  name_en?: string | null;
};

function normalizeLocale(locale: string): "uk" | "ru" | "en" {
  const normalized = String(locale || "").trim().toLowerCase();
  if (normalized.startsWith("ru")) {
    return "ru";
  }
  if (normalized.startsWith("en")) {
    return "en";
  }
  return "uk";
}

function pickFirstNonEmpty(values: Array<string | null | undefined>): string {
  for (const value of values) {
    const text = String(value || "").trim();
    if (text) {
      return text;
    }
  }
  return "";
}

export function getLocalizedProductName(source: LocalizedProductNameSource, locale: string, fallback = "-"): string {
  const baseName = pickFirstNonEmpty([source.display_name, source.name]);
  const language = normalizeLocale(locale);

  const localized =
    language === "ru"
      ? pickFirstNonEmpty([source.name_ru, baseName])
      : language === "en"
        ? pickFirstNonEmpty([source.name_en, source.name_uk, baseName])
        : pickFirstNonEmpty([source.name_uk, baseName]);

  return localized || baseName || fallback;
}
