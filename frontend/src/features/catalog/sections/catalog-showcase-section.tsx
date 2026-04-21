"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { CatalogGridSkeleton } from "@/features/catalog/components/catalog-grid-skeleton";
import { ProductCard } from "@/features/catalog/components/product-card";
import { useCatalogProducts } from "@/features/catalog/hooks/use-catalog-products";
import type { CatalogFilters } from "@/features/catalog/types";

const CATALOG_PAGE_SIZE = 52;

export function CatalogShowcaseSection({
  filters,
  showHeading = true,
}: {
  filters?: CatalogFilters;
  showHeading?: boolean;
}) {
  const tHome = useTranslations("common.home");
  const tCatalog = useTranslations("catalog");
  const [page, setPage] = useState(1);
  const sectionRef = useRef<HTMLElement | null>(null);
  const shouldScrollToTopRef = useRef(false);
  const normalizedFilters = useMemo(() => filters ?? {}, [filters]);
  const filtersKey = useMemo(() => JSON.stringify(normalizedFilters), [normalizedFilters]);
  const { products, totalCount, isLoading } = useCatalogProducts(
    { ...normalizedFilters, page, pageSize: CATALOG_PAGE_SIZE },
    { useActiveVehicle: Boolean(filters) },
  );
  const showSkeleton = isLoading && products.length === 0;
  const pagesCount = useMemo(
    () => Math.max(1, Math.ceil(totalCount / CATALOG_PAGE_SIZE)),
    [totalCount],
  );
  const sectionSpacingClass = showHeading ? "py-8" : "pb-8 pt-0";
  const contentSpacingClass = showHeading ? "mt-4" : "";

  useEffect(() => {
    setPage(1);
  }, [filtersKey]);

  useEffect(() => {
    if (page > pagesCount) {
      setPage(pagesCount);
    }
  }, [page, pagesCount]);

  useEffect(() => {
    if (!shouldScrollToTopRef.current) {
      return;
    }
    shouldScrollToTopRef.current = false;
    sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [page]);

  const changePage = (nextPage: number) => {
    if (nextPage === page) {
      return;
    }
    shouldScrollToTopRef.current = true;
    setPage(nextPage);
  };

  return (
    <section ref={sectionRef} className={`mx-auto max-w-6xl px-4 ${sectionSpacingClass}`}>
      {showHeading ? (
        <>
          <h2 className="text-2xl font-semibold">{tHome("featured")}</h2>
        </>
      ) : null}

      <div className={contentSpacingClass}>
        {showSkeleton ? (
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
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {products.map((product) => (
                    <ProductCard key={product.id} product={product} />
                  ))}
                </div>
                {pagesCount > 1 ? (
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                    <span className="text-xs" style={{ color: "var(--muted)" }}>
                      {tCatalog("pagination.perPage", { count: CATALOG_PAGE_SIZE })}
                    </span>
                    <div className="inline-flex items-center gap-2">
                      <button
                        type="button"
                        className="h-9 rounded-md border px-3 text-sm disabled:opacity-50"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                        disabled={page <= 1}
                        onClick={() => changePage(Math.max(1, page - 1))}
                      >
                        {tCatalog("pagination.prev")}
                      </button>
                      <span className="min-w-[140px] text-center text-sm" style={{ color: "var(--muted)" }}>
                        {tCatalog("pagination.page", { current: page, total: pagesCount })}
                      </span>
                      <button
                        type="button"
                        className="h-9 rounded-md border px-3 text-sm disabled:opacity-50"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                        disabled={page >= pagesCount}
                        onClick={() => changePage(Math.min(pagesCount, page + 1))}
                      >
                        {tCatalog("pagination.next")}
                      </button>
                    </div>
                  </div>
                ) : null}
              </>
            )}
          </>
        )}
      </div>
    </section>
  );
}
