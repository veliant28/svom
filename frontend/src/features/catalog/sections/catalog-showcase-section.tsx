"use client";

import { useTranslations } from "next-intl";

import { CatalogGridSkeleton } from "@/features/catalog/components/catalog-grid-skeleton";
import { ProductCard } from "@/features/catalog/components/product-card";
import { useCatalogProducts } from "@/features/catalog/hooks/use-catalog-products";
import type { CatalogFilters } from "@/features/catalog/types";

export function CatalogShowcaseSection({
  filters,
  showHeading = true,
}: {
  filters?: CatalogFilters & { pageSize?: number };
  showHeading?: boolean;
}) {
  const tHome = useTranslations("common.home");
  const tCatalog = useTranslations("catalog");
  const { products, totalCount, isLoading } = useCatalogProducts(filters ?? { pageSize: 8 });

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      {showHeading ? (
        <>
          <h2 className="text-2xl font-semibold">{tHome("featured")}</h2>
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            {tCatalog("showcaseSubtitle")}
          </p>
        </>
      ) : null}

      <div className="mt-4">
        {isLoading ? (
          <CatalogGridSkeleton />
        ) : (
          <>
            <p className="mb-3 text-sm" style={{ color: "var(--muted)" }}>
              {tCatalog("resultCount", { count: totalCount })}
            </p>
            {products.length === 0 ? (
              <div className="rounded-xl border p-6 text-sm" style={{ borderColor: "var(--border)", color: "var(--muted)" }}>
                {tCatalog("empty")}
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {products.map((product) => (
                  <ProductCard key={product.id} product={product} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
