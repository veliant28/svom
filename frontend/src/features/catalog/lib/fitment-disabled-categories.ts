import type { CategorySummary } from "@/features/catalog/types";

const FITMENT_DISABLED_CATEGORY_SIGNATURES = new Set([
  "автохіміятааксесуари",
  "автохимияиаксессуары",
  "autochemicalsandaccessories",
  "автохімія",
  "автохимия",
  "autochemistry",
  "шинитадиски",
  "шиныидиски",
  "tiresandwheels",
  "автошини",
  "автошины",
  "cartires",
]);

function normalizeCategorySignature(value: string | null | undefined): string {
  const raw = String(value ?? "")
    .trim()
    .toLowerCase();
  if (!raw) {
    return "";
  }
  return raw.replace(/[^0-9a-zа-яіїєґ]+/giu, "");
}

export function isFitmentDisabledCategory(category: CategorySummary | null | undefined): boolean {
  if (!category) {
    return false;
  }

  const nodes = [category, category.parent].filter(Boolean) as Array<Pick<CategorySummary, "slug" | "name">>;
  for (const node of nodes) {
    const candidates = [node.slug, node.name];
    for (const candidate of candidates) {
      const signature = normalizeCategorySignature(candidate);
      if (signature && FITMENT_DISABLED_CATEGORY_SIGNATURES.has(signature)) {
        return true;
      }
    }
  }

  return false;
}
