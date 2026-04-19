export const SUPPLIER_IMPORT_CHIP_BACKGROUND = [
  "color-mix(in srgb, var(--surface) 72%, #2563eb 28%)",
  "color-mix(in srgb, var(--surface) 72%, #16a34a 28%)",
  "color-mix(in srgb, var(--surface) 72%, #f59e0b 28%)",
  "color-mix(in srgb, var(--surface) 72%, #db2777 28%)",
  "color-mix(in srgb, var(--surface) 72%, #7c3aed 28%)",
] as const;

export type UtrFilterMode = "all" | "brands" | "categories" | "models";

export function selectedUtrFilterCount({
  visibleBrands,
  categories,
  models,
}: {
  visibleBrands: number[];
  categories: string[];
  models: string[];
}): number {
  return visibleBrands.length + categories.length + models.length;
}
