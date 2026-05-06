import { CatalogInteractiveSection } from "@/features/catalog/sections/catalog-interactive-section";
import type { BrandSummary, CategorySummary } from "@/features/catalog/types";

type CatalogPageProps = {
  initialBrands?: BrandSummary[];
  initialCategories?: CategorySummary[];
};

export function CatalogPage({ initialBrands = [], initialCategories = [] }: CatalogPageProps) {
  return <CatalogInteractiveSection initialBrands={initialBrands} initialCategories={initialCategories} />;
}
