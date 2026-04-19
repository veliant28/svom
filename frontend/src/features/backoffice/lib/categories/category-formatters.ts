import type { BackofficeCatalogCategory } from "@/features/backoffice/types/catalog.types";

export function getCategoryDisplayName(category: BackofficeCatalogCategory, locale: string): string {
  if (locale === "ru") {
    return category.name_ru || category.name_uk || category.name;
  }
  if (locale === "en") {
    return category.name_en || category.name_uk || category.name;
  }
  return category.name_uk || category.name;
}

export function getCategoryParentDisplayName({
  category,
  parentById,
  locale,
}: {
  category: BackofficeCatalogCategory;
  parentById: Record<string, BackofficeCatalogCategory>;
  locale: string;
}): string {
  if (!category.parent) {
    return "";
  }

  const parentCategory = parentById[category.parent];
  if (!parentCategory) {
    return category.parent_name;
  }

  return getCategoryDisplayName(parentCategory, locale);
}
