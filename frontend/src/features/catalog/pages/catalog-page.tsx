import { CatalogInteractiveSection } from "@/features/catalog/sections/catalog-interactive-section";
import type { CategorySummary } from "@/features/catalog/types";

type CatalogPageProps = {
  initialCategories?: CategorySummary[];
};

export function CatalogPage({ initialCategories = [] }: CatalogPageProps) {
  return <CatalogInteractiveSection initialCategories={initialCategories} />;
}
