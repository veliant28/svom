"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";

import { CatalogGridSkeleton } from "@/features/catalog/components/catalog-grid-skeleton";
import { ProductCard } from "@/features/catalog/components/product-card";
import { useCatalogWarmup } from "@/features/catalog/hooks/use-catalog-warmup";
import { useCatalogProducts } from "@/features/catalog/hooks/use-catalog-products";
import {
  clearCatalogReturnState,
  readMatchingCatalogReturnState,
  restoreCatalogProductScroll,
  scrollCatalogListToTop,
  scrollCatalogPageToTop,
  type CatalogReturnState,
} from "@/features/catalog/lib/catalog-navigation-state";
import type { CatalogFilters } from "@/features/catalog/types";
import { usePathname, useRouter } from "@/i18n/navigation";

const CATALOG_PAGE_SIZE = 52;

function parseCatalogPage(searchParams: URLSearchParams): number {
  const value = Number(searchParams.get("page") || "1");
  if (!Number.isFinite(value) || value < 1) {
    return 1;
  }
  return Math.floor(value);
}

export function CatalogShowcaseSection({
  filters,
  showHeading = true,
  scrollAnchorRef,
}: {
  filters?: CatalogFilters;
  showHeading?: boolean;
  scrollAnchorRef?: RefObject<HTMLElement | null>;
}) {
  const tHome = useTranslations("common.home");
  const tCatalog = useTranslations("catalog");
  const router = useRouter();
  const { updateCatalogWarmupScope } = useCatalogWarmup();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const syncPageWithUrl = Boolean(filters);
  const [localPage, setLocalPage] = useState(1);
  const [visibleProductIds, setVisibleProductIds] = useState<string[]>([]);
  const [catalogReturnState, setCatalogReturnState] = useState<CatalogReturnState | null>(() =>
    readMatchingCatalogReturnState(),
  );
  const [deferCachedRevalidation, setDeferCachedRevalidation] = useState(() => Boolean(readMatchingCatalogReturnState()));
  const sectionRef = useRef<HTMLElement | null>(null);
  const productCardRefMap = useRef<Map<string, HTMLDivElement>>(new Map());
  const visibleCardSetRef = useRef<Set<string>>(new Set());
  const restoredReturnStateRef = useRef<string>("");
  const getListTopScrollNode = useCallback(
    () => scrollAnchorRef?.current ?? sectionRef.current,
    [scrollAnchorRef],
  );
  const normalizedFilters = useMemo(() => {
    if (filters) {
      return filters;
    }
    if (showHeading) {
      return { popular: true } satisfies CatalogFilters;
    }
    return {};
  }, [filters, showHeading]);
  const queryString = searchParams.toString();
  const urlPage = parseCatalogPage(new URLSearchParams(queryString));
  const page = syncPageWithUrl ? urlPage : localPage;
  const { products, totalCount, isLoading, cacheKey } = useCatalogProducts(
    { ...normalizedFilters, page, pageSize: CATALOG_PAGE_SIZE },
    {
      useActiveVehicle: true,
      deferCachedRevalidation,
    },
  );
  const productIds = useMemo(() => products.map((product) => product.id), [products]);
  const showSkeleton = isLoading && products.length === 0;
  const pagesCount = useMemo(
    () => Math.max(1, Math.ceil(totalCount / CATALOG_PAGE_SIZE)),
    [totalCount],
  );
  const sectionSpacingClass = showHeading ? "py-8" : "pb-8 pt-0";
  const contentSpacingClass = showHeading ? "mt-4" : "";

  useEffect(() => {
    if (!syncPageWithUrl || typeof window === "undefined" || !("scrollRestoration" in window.history)) {
      return;
    }
    const previousScrollRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    return () => {
      window.history.scrollRestoration = previousScrollRestoration;
    };
  }, [syncPageWithUrl]);

  useEffect(() => {
    if (!syncPageWithUrl) {
      return;
    }
    const matchingState = readMatchingCatalogReturnState();
    setCatalogReturnState(matchingState);
    setDeferCachedRevalidation(Boolean(matchingState));
    restoredReturnStateRef.current = "";
    if (!matchingState) {
      scrollCatalogPageToTop();
    }
  }, [getListTopScrollNode, pathname, queryString, syncPageWithUrl]);

  useEffect(() => {
    if (!syncPageWithUrl || !catalogReturnState || isLoading) {
      return;
    }
    const restoreKey = `${catalogReturnState.catalogUrl}:${catalogReturnState.productId}:${catalogReturnState.savedAt}`;
    if (restoredReturnStateRef.current === restoreKey) {
      return;
    }

    let frameOne = 0;
    let frameTwo = 0;
    frameOne = window.requestAnimationFrame(() => {
      frameTwo = window.requestAnimationFrame(() => {
        const productNode = productCardRefMap.current.get(catalogReturnState.productId) ?? null;
        if (!restoreCatalogProductScroll(catalogReturnState, productNode)) {
          scrollCatalogListToTop(getListTopScrollNode());
        }
        restoredReturnStateRef.current = restoreKey;
        clearCatalogReturnState();
        setCatalogReturnState(null);
      });
    });

    return () => {
      window.cancelAnimationFrame(frameOne);
      window.cancelAnimationFrame(frameTwo);
    };
  }, [catalogReturnState, getListTopScrollNode, isLoading, productIds, syncPageWithUrl]);

  useEffect(() => {
    if (!syncPageWithUrl || productIds.length === 0) {
      setVisibleProductIds([]);
      visibleCardSetRef.current.clear();
      return;
    }

    const syncVisibleByCurrentOrder = () => {
      const nextVisible = productIds.filter((id) => visibleCardSetRef.current.has(id));
      setVisibleProductIds((previous) => (previous.join("|") === nextVisible.join("|") ? previous : nextVisible));
    };

    if (typeof IntersectionObserver === "undefined") {
      const fallback = productIds.slice(0, 12);
      setVisibleProductIds((previous) => (previous.join("|") === fallback.join("|") ? previous : fallback));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        let changed = false;
        for (const entry of entries) {
          const id = (entry.target as HTMLElement).dataset.productId;
          if (!id) {
            continue;
          }
          if (entry.isIntersecting) {
            if (!visibleCardSetRef.current.has(id)) {
              visibleCardSetRef.current.add(id);
              changed = true;
            }
          } else if (visibleCardSetRef.current.delete(id)) {
            changed = true;
          }
        }
        if (changed) {
          syncVisibleByCurrentOrder();
        }
      },
      { root: null, threshold: 0.5 },
    );

    visibleCardSetRef.current.clear();
    for (const [id, node] of productCardRefMap.current.entries()) {
      if (productIds.includes(id)) {
        observer.observe(node);
      }
    }
    syncVisibleByCurrentOrder();

    return () => {
      observer.disconnect();
    };
  }, [productIds, syncPageWithUrl]);

  const setProductCardNode = useCallback((productId: string, node: HTMLDivElement | null) => {
    if (!node) {
      productCardRefMap.current.delete(productId);
      visibleCardSetRef.current.delete(productId);
      return;
    }
    node.dataset.productId = productId;
    productCardRefMap.current.set(productId, node);
  }, []);

  useEffect(() => {
    if (!syncPageWithUrl || isLoading || productIds.length === 0) {
      return;
    }
    const prioritizedVisibleIds = (visibleProductIds.length > 0 ? visibleProductIds : productIds).slice(0, 12);
    updateCatalogWarmupScope({
      cacheKey,
      productIds,
      visibleProductIds: prioritizedVisibleIds,
      totalCount,
    });
  }, [
    cacheKey,
    isLoading,
    productIds,
    syncPageWithUrl,
    totalCount,
    updateCatalogWarmupScope,
    visibleProductIds,
  ]);

  useEffect(() => {
    if (!isLoading && page > pagesCount) {
      if (!syncPageWithUrl) {
        setLocalPage(pagesCount);
        return;
      }
      const nextParams = new URLSearchParams(searchParams.toString());
      if (pagesCount <= 1) {
        nextParams.delete("page");
      } else {
        nextParams.set("page", String(pagesCount));
      }
      const query = nextParams.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    }
  }, [isLoading, page, pagesCount, pathname, router, searchParams, syncPageWithUrl]);

  const changePage = (nextPage: number) => {
    if (nextPage === page) {
      return;
    }
    if (!syncPageWithUrl) {
      if (typeof window !== "undefined") {
        scrollCatalogPageToTop();
      }
      setLocalPage(nextPage);
      return;
    }
    const nextParams = new URLSearchParams(searchParams.toString());
    if (nextPage <= 1) {
      nextParams.delete("page");
    } else {
      nextParams.set("page", String(nextPage));
    }
    const query = nextParams.toString();
    const nextUrl = query ? `${pathname}?${query}` : pathname;
    setDeferCachedRevalidation(false);
    scrollCatalogPageToTop();
    router.push(nextUrl, { scroll: false });
  };

  return (
    <section ref={sectionRef} data-catalog-showcase className={`mx-auto max-w-6xl px-4 ${sectionSpacingClass}`}>
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
                    <div key={product.id} ref={(node) => setProductCardNode(product.id, node)}>
                      <ProductCard product={product} preserveCatalogQuery={syncPageWithUrl} />
                    </div>
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
