export const PAGE_SIZE_OPTIONS = [15, 25, 50, 100, 500] as const;

export type SupplierProductsPageSize = (typeof PAGE_SIZE_OPTIONS)[number];

export function priceDigitsOnly(value: string): string {
  const numeric = value.replace(/[^\d.,-]/g, "").trim();
  return numeric || value;
}
