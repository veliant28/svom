"use client";

import { useTranslations } from "next-intl";

import { CatalogFiltersPanel } from "@/features/catalog/components/catalog-filters-panel";
import { CatalogGarageFitmentPanel } from "@/features/catalog/components/catalog-garage-fitment-panel";
import { ProductCard } from "@/features/catalog/components/product-card";
import { useCatalogFilters } from "@/features/catalog/hooks/use-catalog-filters";
import { useCatalogProducts } from "@/features/catalog/hooks/use-catalog-products";

function hasSearchCriteria(filters: ReturnType<typeof useCatalogFilters>["filters"]): boolean {
  return Boolean(
    filters.q ||
      filters.brand ||
      filters.category ||
      filters.garage_vehicle ||
      filters.modification ||
      filters.fitment,
  );
}

export function SearchPage() {
  const t = useTranslations("search");
  const { filters } = useCatalogFilters();
  const isEnabled = hasSearchCriteria(filters);
  const { products, totalCount, isLoading } = useCatalogProducts({ ...filters, pageSize: 24 }, { enabled: isEnabled });

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        {t("subtitle")}
      </p>

      <div className="mt-4">
        <CatalogFiltersPanel />
        <CatalogGarageFitmentPanel
          resultCount={isEnabled ? totalCount : undefined}
          isResultCountLoading={isEnabled && isLoading}
        />
      </div>

      {!isEnabled ? (
        <p className="mt-4 text-sm" style={{ color: "var(--muted)" }}>
          {t("states.noCriteria")}
        </p>
      ) : (
        <>
          <p className="mt-4 text-sm" style={{ color: "var(--muted)" }}>
            {isLoading ? t("states.searching") : t("states.found", { count: totalCount })}
          </p>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {products.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}
