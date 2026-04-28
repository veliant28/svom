"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { requestUtrProductEnrichment } from "@/features/catalog/api/request-utr-enrichment";
import { readCachedCatalogPayload, writeCachedCatalogPayload } from "@/features/catalog/lib/catalog-page-cache";

const CATALOG_WARMUP_VISIBLE_LIMIT = 12;
const CATALOG_WARMUP_MAX_DURATION_MS = 45 * 1000;

type CatalogWarmupScope = {
  cacheKey: string;
  productIds: string[];
  visibleProductIds: string[];
  totalCount: number;
};

type CatalogWarmupContextValue = {
  updateCatalogWarmupScope: (scope: CatalogWarmupScope) => void;
};

const CatalogWarmupContext = createContext<CatalogWarmupContextValue | null>(null);

function pickPriorityIds(scope: CatalogWarmupScope): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];

  for (const id of scope.visibleProductIds) {
    if (!id || seen.has(id)) {
      continue;
    }
    seen.add(id);
    ordered.push(id);
    if (ordered.length >= CATALOG_WARMUP_VISIBLE_LIMIT) {
      return ordered;
    }
  }

  for (const id of scope.productIds) {
    if (!id || seen.has(id)) {
      continue;
    }
    seen.add(id);
    ordered.push(id);
    if (ordered.length >= CATALOG_WARMUP_VISIBLE_LIMIT) {
      break;
    }
  }

  return ordered;
}

export function CatalogWarmupProvider({ children }: { children: React.ReactNode }) {
  const [scope, setScope] = useState<CatalogWarmupScope | null>(null);
  const scopeRef = useRef<CatalogWarmupScope | null>(null);
  const lastRunSignatureRef = useRef<string>("");
  const lastRunStartedAtRef = useRef<number>(0);

  const updateCatalogWarmupScope = useCallback((nextScope: CatalogWarmupScope) => {
    const normalized: CatalogWarmupScope = {
      cacheKey: nextScope.cacheKey,
      productIds: Array.from(new Set(nextScope.productIds.filter(Boolean))),
      visibleProductIds: Array.from(new Set(nextScope.visibleProductIds.filter(Boolean))),
      totalCount: nextScope.totalCount,
    };
    scopeRef.current = normalized;
    setScope((previous) => {
      if (
        previous
        && previous.cacheKey === normalized.cacheKey
        && previous.totalCount === normalized.totalCount
        && previous.productIds.join("|") === normalized.productIds.join("|")
        && previous.visibleProductIds.join("|") === normalized.visibleProductIds.join("|")
      ) {
        return previous;
      }
      return normalized;
    });
  }, []);

  useEffect(() => {
    if (!scope || scope.productIds.length === 0) {
      return;
    }
    const scopeKey = scope.cacheKey;
    const runSignature = `${scopeKey}::${pickPriorityIds(scope).join("|")}`;
    const startedAtNow = Date.now();
    if (
      lastRunSignatureRef.current === runSignature
      && startedAtNow - lastRunStartedAtRef.current < 1500
    ) {
      return;
    }
    lastRunSignatureRef.current = runSignature;
    lastRunStartedAtRef.current = startedAtNow;

    let isCancelled = false;
    const startedAt = startedAtNow;

    const shouldContinue = (statuses: Awaited<ReturnType<typeof requestUtrProductEnrichment>>) =>
      statuses.some(
        (item) =>
          item.needs_enrichment
          || item.status === "queued"
          || item.status === "in_progress"
          || item.queued
          || (!!item.utr_detail_id && !item.applicability_ready),
      );

    const applyStatusesToCache = (statuses: Awaited<ReturnType<typeof requestUtrProductEnrichment>>) => {
      if (isCancelled) {
        return;
      }
      const currentScope = scopeRef.current;
      if (!currentScope || currentScope.cacheKey !== scopeKey) {
        return;
      }
      const currentCached = readCachedCatalogPayload(currentScope.cacheKey);
      if (!currentCached || currentCached.products.length === 0) {
        return;
      }

      const statusByProductId = new Map(statuses.map((item) => [item.product_id, item]));
      let touched = false;
      const nextProducts = currentCached.products.map((product) => {
        const status = statusByProductId.get(product.id);
        if (!status) {
          return product;
        }
        const hasNewImage = !!status.primary_image && status.primary_image !== product.primary_image;
        const hasNewFitmentData = status.applicability_ready && !product.has_fitment_data;
        if (!hasNewImage && !hasNewFitmentData) {
          return product;
        }
        touched = true;
        return {
          ...product,
          primary_image: hasNewImage ? status.primary_image : product.primary_image,
          has_fitment_data: hasNewFitmentData ? true : product.has_fitment_data,
        };
      });

      if (!touched) {
        return;
      }

      writeCachedCatalogPayload(currentScope.cacheKey, {
        products: nextProducts,
        totalCount: currentCached.totalCount,
      });
    };

    async function runWarmup() {
      let attempt = 0;
      while (!isCancelled) {
        if (typeof document !== "undefined" && document.hidden) {
          return;
        }
        if (Date.now() - startedAt > CATALOG_WARMUP_MAX_DURATION_MS) {
          return;
        }

        const currentScope = scopeRef.current;
        if (!currentScope || currentScope.cacheKey !== scopeKey) {
          return;
        }
        const priorityIds = pickPriorityIds(currentScope);
        if (priorityIds.length === 0) {
          return;
        }

        let statuses: Awaited<ReturnType<typeof requestUtrProductEnrichment>>;
        try {
          statuses = await requestUtrProductEnrichment(priorityIds, true, "catalog");
        } catch {
          return;
        }
        if (isCancelled) {
          return;
        }
        applyStatusesToCache(statuses);

        if (!shouldContinue(statuses)) {
          return;
        }

        attempt += 1;
        const delayMs = attempt < 3 ? 1000 : attempt < 7 ? 2000 : 3000;
        await new Promise((resolve) => window.setTimeout(resolve, delayMs));
      }
    }

    void runWarmup();

    return () => {
      isCancelled = true;
    };
  }, [scope]);

  const value = useMemo<CatalogWarmupContextValue>(
    () => ({ updateCatalogWarmupScope }),
    [updateCatalogWarmupScope],
  );

  return <CatalogWarmupContext.Provider value={value}>{children}</CatalogWarmupContext.Provider>;
}

export function useCatalogWarmup() {
  const context = useContext(CatalogWarmupContext);
  if (!context) {
    return {
      updateCatalogWarmupScope: () => {
        // noop fallback for non-storefront trees
      },
    };
  }
  return context;
}
