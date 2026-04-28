"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";

import { CatalogGridSkeleton } from "@/features/catalog/components/catalog-grid-skeleton";
import { ProductCard } from "@/features/catalog/components/product-card";
import { useCatalogWarmup } from "@/features/catalog/hooks/use-catalog-warmup";
import { useCatalogProducts } from "@/features/catalog/hooks/use-catalog-products";
import type { CatalogFilters } from "@/features/catalog/types";
import { usePathname, useRouter } from "@/i18n/navigation";

const CATALOG_PAGE_SIZE = 52;
const CATALOG_SCROLL_KEY_PREFIX = "catalog:scroll:";
const CATALOG_SCROLL_SKIP_RESTORE_ONCE_KEY = "catalog:scroll:skip_restore_once";
const CATALOG_SCROLL_TTL_MS = 30 * 60 * 1000;
const CATALOG_RESTORE_MAX_WAIT_MS = 120 * 1000;

type CatalogScrollState = {
  y: number;
  savedAt: number;
};

function buildCatalogScrollKey(pathname: string, query: string): string {
  return `${CATALOG_SCROLL_KEY_PREFIX}${query ? `${pathname}?${query}` : pathname}`;
}

function normalizeCatalogUrl(rawUrl: string): string {
  if (!rawUrl) {
    return "";
  }
  try {
    const url = rawUrl.startsWith("http://") || rawUrl.startsWith("https://")
      ? new URL(rawUrl)
      : new URL(rawUrl, "http://localhost");
    const params = new URLSearchParams(url.search);
    const sortedEntries = Array.from(params.entries()).sort(([a], [b]) => a.localeCompare(b));
    const normalizedParams = new URLSearchParams();
    for (const [key, value] of sortedEntries) {
      normalizedParams.append(key, value);
    }
    const query = normalizedParams.toString();
    return query ? `${url.pathname}?${query}` : url.pathname;
  } catch {
    return rawUrl;
  }
}

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
}: {
  filters?: CatalogFilters;
  showHeading?: boolean;
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
  const sectionRef = useRef<HTMLElement | null>(null);
  const productCardRefMap = useRef<Map<string, HTMLDivElement>>(new Map());
  const visibleCardSetRef = useRef<Set<string>>(new Set());
  const shouldScrollToTopRef = useRef(false);
  const restoredScrollKeyRef = useRef<string | null>(null);
  const consumedForcedScrollKeyRef = useRef<string | null>(null);
  const skipRestoreForScrollKeyRef = useRef<string | null>(null);
  const normalizedFilters = useMemo(() => filters ?? {}, [filters]);
  const queryString = searchParams.toString();
  const urlPage = parseCatalogPage(new URLSearchParams(queryString));
  const page = syncPageWithUrl ? urlPage : localPage;
  const browserCatalogUrl = useMemo(() => {
    if (typeof window !== "undefined") {
      return `${window.location.pathname}${window.location.search}`;
    }
    return queryString ? `${pathname}?${queryString}` : pathname;
  }, [pathname, queryString]);
  const normalizedCatalogUrl = useMemo(() => normalizeCatalogUrl(browserCatalogUrl), [browserCatalogUrl]);
  const scrollStorageKey = useMemo(() => buildCatalogScrollKey(normalizedCatalogUrl, ""), [normalizedCatalogUrl]);
  const legacyScrollStorageKey = useMemo(() => buildCatalogScrollKey(browserCatalogUrl, ""), [browserCatalogUrl]);
  const { products, totalCount, isLoading, cacheKey } = useCatalogProducts(
    { ...normalizedFilters, page, pageSize: CATALOG_PAGE_SIZE },
    {
      useActiveVehicle: Boolean(
        normalizedFilters.fitment
          || normalizedFilters.garage_vehicle
          || normalizedFilters.car_modification
          || normalizedFilters.modification,
      ),
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
  const forcedScrollFromQuery = useMemo(() => {
    const raw = searchParams.get("_cs");
    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed < 0) {
      return null;
    }
    return Math.floor(parsed);
  }, [searchParams]);

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
      router.replace(query ? `${pathname}?${query}` : pathname);
    }
  }, [isLoading, page, pagesCount, pathname, router, searchParams, syncPageWithUrl]);

  useEffect(() => {
    if (!shouldScrollToTopRef.current) {
      return;
    }
    shouldScrollToTopRef.current = false;
    sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [page]);

  useEffect(() => {
    if (!syncPageWithUrl || forcedScrollFromQuery === null || typeof window === "undefined") {
      return;
    }
    const forcedScrollKey = `${pathname}?${queryString}`;
    if (consumedForcedScrollKeyRef.current === forcedScrollKey) {
      return;
    }

    let timer: number | null = null;
    const startedAt = Date.now();
    const restore = () => {
      const maxScrollableY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      const hasEnoughHeight = maxScrollableY >= forcedScrollFromQuery;
      const timedOut = Date.now() - startedAt >= CATALOG_RESTORE_MAX_WAIT_MS;
      if (hasEnoughHeight || timedOut) {
        const finalTarget = Math.min(forcedScrollFromQuery, maxScrollableY);
        window.scrollTo({ top: finalTarget, behavior: "auto" });
        const nextParams = new URLSearchParams(queryString);
        nextParams.delete("_cs");
        const nextQuery = nextParams.toString();
        const nextUrl = nextQuery ? `${pathname}?${nextQuery}` : pathname;
        window.history.replaceState(window.history.state, "", nextUrl);
        consumedForcedScrollKeyRef.current = forcedScrollKey;
        return;
      }
      timer = window.setTimeout(restore, 100);
    };

    restore();
    return () => {
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [forcedScrollFromQuery, pathname, queryString, syncPageWithUrl]);

  useEffect(() => {
    if (!syncPageWithUrl) {
      return;
    }
    let lastKnownY = typeof window !== "undefined" ? window.scrollY : 0;

    const writeScrollState = () => {
      if (typeof window === "undefined") {
        return;
      }
      try {
        window.sessionStorage.setItem(
          scrollStorageKey,
          JSON.stringify({
            y: lastKnownY,
            savedAt: Date.now(),
          } satisfies CatalogScrollState),
        );
      } catch {
        // Best-effort cache only.
      }
    };

    let ticking = false;
    const onScroll = () => {
      if (ticking) {
        return;
      }
      ticking = true;
      window.requestAnimationFrame(() => {
        ticking = false;
        lastKnownY = window.scrollY;
        writeScrollState();
      });
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      writeScrollState();
    };
  }, [scrollStorageKey, syncPageWithUrl]);

  useEffect(() => {
    if (!syncPageWithUrl || typeof window === "undefined") {
      return;
    }
    try {
      const skipOnceKey = window.sessionStorage.getItem(CATALOG_SCROLL_SKIP_RESTORE_ONCE_KEY);
      if (skipOnceKey && skipOnceKey === scrollStorageKey) {
        window.sessionStorage.removeItem(CATALOG_SCROLL_SKIP_RESTORE_ONCE_KEY);
        skipRestoreForScrollKeyRef.current = null;
        restoredScrollKeyRef.current = scrollStorageKey;
        window.scrollTo({ top: 0, behavior: "auto" });
        return;
      }
    } catch {
      // ignore storage failures
    }
    if (skipRestoreForScrollKeyRef.current === scrollStorageKey) {
      skipRestoreForScrollKeyRef.current = null;
      restoredScrollKeyRef.current = scrollStorageKey;
      window.scrollTo({ top: 0, behavior: "auto" });
      return;
    }
    if (restoredScrollKeyRef.current === scrollStorageKey) {
      return;
    }

    let scrollState: CatalogScrollState | null = null;
    try {
      const raw =
        window.sessionStorage.getItem(scrollStorageKey)
        || window.sessionStorage.getItem(legacyScrollStorageKey);
      if (!raw) {
        return;
      }
      scrollState = JSON.parse(raw) as CatalogScrollState;
    } catch {
      return;
    }

    if (
      !scrollState
      || typeof scrollState.y !== "number"
      || scrollState.y < 0
      || typeof scrollState.savedAt !== "number"
      || Date.now() - scrollState.savedAt > CATALOG_SCROLL_TTL_MS
    ) {
      return;
    }

    const targetY = scrollState.y;
    const startedAt = Date.now();
    let timer: number | null = null;

    const tryRestore = () => {
      const maxScrollableY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      const hasEnoughHeight = maxScrollableY >= targetY;
      const timedOut = Date.now() - startedAt >= CATALOG_RESTORE_MAX_WAIT_MS;
      if (hasEnoughHeight || timedOut) {
        const finalTarget = Math.min(targetY, maxScrollableY);
        window.scrollTo({ top: finalTarget, behavior: "auto" });
        restoredScrollKeyRef.current = scrollStorageKey;
        return;
      }
      timer = window.setTimeout(tryRestore, 120);
    };

    tryRestore();
    return () => {
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [browserCatalogUrl, legacyScrollStorageKey, scrollStorageKey, syncPageWithUrl]);

  const changePage = (nextPage: number) => {
    if (nextPage === page) {
      return;
    }
    shouldScrollToTopRef.current = true;
    sectionRef.current?.scrollIntoView({ behavior: "auto", block: "start" });
    if (!syncPageWithUrl) {
      setLocalPage(nextPage);
      return;
    }
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("_cs");
    if (nextPage <= 1) {
      nextParams.delete("page");
    } else {
      nextParams.set("page", String(nextPage));
    }
    const query = nextParams.toString();
    const nextUrl = query ? `${pathname}?${query}` : pathname;
    const normalizedNextUrl = normalizeCatalogUrl(nextUrl);
    const nextScrollStorageKey = buildCatalogScrollKey(normalizedNextUrl, "");
    skipRestoreForScrollKeyRef.current = nextScrollStorageKey;
    try {
      window.sessionStorage.setItem(CATALOG_SCROLL_SKIP_RESTORE_ONCE_KEY, nextScrollStorageKey);
      window.sessionStorage.removeItem(nextScrollStorageKey);
    } catch {
      // ignore storage failures
    }
    router.replace(nextUrl);
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
