"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

const CATALOG_WARMUP_VISIBLE_LIMIT = 12;

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
    const runSignature = `${scope.cacheKey}::${pickPriorityIds(scope).join("|")}`;
    const startedAtNow = Date.now();
    if (
      lastRunSignatureRef.current === runSignature
      && startedAtNow - lastRunStartedAtRef.current < 1500
    ) {
      return;
    }
    lastRunSignatureRef.current = runSignature;
    lastRunStartedAtRef.current = startedAtNow;
    // UTR catalog warmup is intentionally disabled.
    // Catalog compatibility/images/attributes are sourced from Auto_DB/GPL only.
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
