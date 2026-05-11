"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
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
const HOME_POPULAR_PAGE_SIZE = 20;
const CAROUSEL_AUTO_ADVANCE_MS = 7000;

function resolveCardsPerSlide(width: number): number {
  if (width >= 1024) {
    return 4;
  }
  if (width >= 640) {
    return 2;
  }
  return 1;
}

function parseCatalogPage(searchParams: URLSearchParams): number {
  const value = Number(searchParams?.get("page") || "1");
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
  const isPopularCarouselMode = showHeading && !filters;
  const [localPage, setLocalPage] = useState(1);
  const [visibleProductIds, setVisibleProductIds] = useState<string[]>([]);
  const [cardsPerSlide, setCardsPerSlide] = useState(4);
  const [carouselIndex, setCarouselIndex] = useState(0);
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
    return {};
  }, [filters]);
  const queryString = searchParams?.toString() ?? "";
  const urlPage = parseCatalogPage(new URLSearchParams(queryString));
  const page = syncPageWithUrl ? urlPage : localPage;
  const pageSize = isPopularCarouselMode ? HOME_POPULAR_PAGE_SIZE : CATALOG_PAGE_SIZE;
  const { products, totalCount, isLoading, cacheKey } = useCatalogProducts(
    { ...normalizedFilters, page, pageSize },
    {
      useActiveVehicle: true,
      deferCachedRevalidation,
      useHomePopularEndpoint: isPopularCarouselMode,
    },
  );
  const productIds = useMemo(() => products.map((product) => product.id), [products]);
  const showSkeleton = isLoading && products.length === 0;
  const pagesCount = useMemo(
    () => Math.max(1, Math.ceil(totalCount / pageSize)),
    [pageSize, totalCount],
  );
  const carouselSlides = useMemo(() => {
    if (!isPopularCarouselMode) {
      return [];
    }
    const chunkSize = Math.max(1, cardsPerSlide);
    const chunks: typeof products[] = [];
    for (let index = 0; index < products.length; index += chunkSize) {
      chunks.push(products.slice(index, index + chunkSize));
    }
    return chunks;
  }, [cardsPerSlide, isPopularCarouselMode, products]);
  const canSlideCarousel = carouselSlides.length > 1;
  const sectionSpacingClass = showHeading ? "py-8" : "pb-8 pt-0";
  const contentSpacingClass = showHeading ? "mt-4" : "";

  useEffect(() => {
    if (!isPopularCarouselMode || typeof window === "undefined") {
      return;
    }

    const updateCardsPerSlide = () => {
      const nextValue = resolveCardsPerSlide(window.innerWidth);
      setCardsPerSlide((previous) => (previous === nextValue ? previous : nextValue));
    };

    updateCardsPerSlide();
    window.addEventListener("resize", updateCardsPerSlide);
    return () => {
      window.removeEventListener("resize", updateCardsPerSlide);
    };
  }, [isPopularCarouselMode]);

  useEffect(() => {
    if (!isPopularCarouselMode) {
      return;
    }
    setCarouselIndex((previous) => {
      if (carouselSlides.length <= 1) {
        return 0;
      }
      return previous >= carouselSlides.length ? 0 : previous;
    });
  }, [carouselSlides.length, isPopularCarouselMode]);

  useEffect(() => {
    if (!isPopularCarouselMode || !canSlideCarousel) {
      return;
    }
    const intervalId = window.setInterval(() => {
      setCarouselIndex((previous) => (previous + 1) % carouselSlides.length);
    }, CAROUSEL_AUTO_ADVANCE_MS);
    return () => {
      window.clearInterval(intervalId);
    };
  }, [canSlideCarousel, carouselSlides.length, isPopularCarouselMode]);

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
      const nextParams = new URLSearchParams(searchParams?.toString() ?? "");
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
    const nextParams = new URLSearchParams(searchParams?.toString() ?? "");
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

  const goToPreviousCarouselSlide = useCallback(() => {
    if (!canSlideCarousel) {
      return;
    }
    setCarouselIndex((previous) => (previous - 1 + carouselSlides.length) % carouselSlides.length);
  }, [canSlideCarousel, carouselSlides.length]);

  const goToNextCarouselSlide = useCallback(() => {
    if (!canSlideCarousel) {
      return;
    }
    setCarouselIndex((previous) => (previous + 1) % carouselSlides.length);
  }, [canSlideCarousel, carouselSlides.length]);

  return (
    <section ref={sectionRef} data-catalog-showcase className={`mx-auto max-w-6xl px-4 ${sectionSpacingClass}`}>
      {showHeading ? (
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-2xl font-semibold">{tHome("featured")}</h2>
          {isPopularCarouselMode ? (
            <div className="inline-flex items-center gap-2">
              <button
                type="button"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border disabled:opacity-50"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                onClick={goToPreviousCarouselSlide}
                disabled={!canSlideCarousel}
                aria-label={tCatalog("pagination.prev")}
                title={tCatalog("pagination.prev")}
              >
                <ChevronLeft size={16} />
              </button>
              <button
                type="button"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border disabled:opacity-50"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                onClick={goToNextCarouselSlide}
                disabled={!canSlideCarousel}
                aria-label={tCatalog("pagination.next")}
                title={tCatalog("pagination.next")}
              >
                <ChevronRight size={16} />
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className={contentSpacingClass}>
        {showSkeleton ? (
          <CatalogGridSkeleton />
        ) : (
          <>
            {!isPopularCarouselMode ? (
              <p className="mb-3 text-sm" style={{ color: "var(--muted)" }}>
                {tCatalog("resultCount", { count: totalCount })}
              </p>
            ) : null}
            {products.length === 0 ? (
              <div className="rounded-xl border p-6 text-sm" style={{ borderColor: "var(--border)", color: "var(--muted)" }}>
                {tCatalog("empty")}
              </div>
            ) : (
              <>
                {isPopularCarouselMode ? (
                  <div className="overflow-hidden">
                    <div
                      className="flex transition-transform duration-500 ease-out"
                      style={{ transform: `translateX(-${carouselIndex * 100}%)` }}
                    >
                      {carouselSlides.map((slide, slideIndex) => (
                        <div key={`catalog-slide-${slideIndex}`} className="min-w-full">
                          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                            {slide.map((product) => (
                              <div key={product.id} ref={(node) => setProductCardNode(product.id, node)}>
                                <ProductCard product={product} preserveCatalogQuery={syncPageWithUrl} />
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {products.map((product) => (
                      <div key={product.id} ref={(node) => setProductCardNode(product.id, node)}>
                        <ProductCard product={product} preserveCatalogQuery={syncPageWithUrl} />
                      </div>
                    ))}
                  </div>
                )}
                {!isPopularCarouselMode && pagesCount > 1 ? (
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                    <span className="text-xs" style={{ color: "var(--muted)" }}>
                      {tCatalog("pagination.perPage", { count: pageSize })}
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
