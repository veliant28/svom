import type { CatalogFilters } from "@/features/catalog/types";

const BOOLEAN_FILTER_KEYS = ["is_featured", "is_new", "is_bestseller"] as const;

function parseBoolean(value: string | null): boolean | undefined {
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  return undefined;
}

export function parseCatalogFilters(searchParams: URLSearchParams): CatalogFilters {
  return {
    q: searchParams.get("q") || undefined,
    brand: searchParams.get("brand") || undefined,
    category: searchParams.get("category") || undefined,
    min_price: searchParams.get("min_price") || undefined,
    max_price: searchParams.get("max_price") || undefined,
    is_featured: parseBoolean(searchParams.get("is_featured")),
    is_new: parseBoolean(searchParams.get("is_new")),
    is_bestseller: parseBoolean(searchParams.get("is_bestseller")),
    modification: searchParams.get("modification") || undefined,
    garage_vehicle: searchParams.get("garage_vehicle") || undefined,
    fitment: (searchParams.get("fitment") as CatalogFilters["fitment"]) || undefined,
  };
}

export function buildCatalogFiltersQuery(filters: CatalogFilters): URLSearchParams {
  const params = new URLSearchParams();

  const stringFields: Array<keyof CatalogFilters> = [
    "q",
    "brand",
    "category",
    "min_price",
    "max_price",
    "modification",
    "garage_vehicle",
    "fitment",
  ];
  stringFields.forEach((field) => {
    const value = filters[field];
    if (typeof value === "string" && value.trim()) {
      params.set(field, value.trim());
    }
  });

  BOOLEAN_FILTER_KEYS.forEach((field) => {
    const value = filters[field];
    if (typeof value === "boolean") {
      params.set(field, value ? "true" : "false");
    }
  });

  return params;
}
