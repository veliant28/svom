"use client";

import type { CatalogProduct } from "@/features/catalog/types";

export const CATALOG_CACHE_TTL_MS = 10 * 60 * 1000;
export const CATALOG_CACHE_KEY_PREFIX = "catalog:products:v2:";
export const CATALOG_CACHE_UPDATED_EVENT = "catalog:cache-updated";

export type CachedCatalogPayload = {
  savedAt: number;
  products: CatalogProduct[];
  totalCount: number;
};

export function buildCatalogCacheKey(paramsKey: string): string {
  return `${CATALOG_CACHE_KEY_PREFIX}${paramsKey}`;
}

export function readCachedCatalogPayload(cacheKey: string): CachedCatalogPayload | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(cacheKey);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as CachedCatalogPayload;
    if (!parsed || !Array.isArray(parsed.products) || typeof parsed.totalCount !== "number" || typeof parsed.savedAt !== "number") {
      return null;
    }
    if (Date.now() - parsed.savedAt > CATALOG_CACHE_TTL_MS) {
      window.sessionStorage.removeItem(cacheKey);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function writeCachedCatalogPayload(cacheKey: string, payload: Omit<CachedCatalogPayload, "savedAt">): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    const nextPayload = {
      ...payload,
      savedAt: Date.now(),
    } satisfies CachedCatalogPayload;
    window.sessionStorage.setItem(
      cacheKey,
      JSON.stringify(nextPayload),
    );
    window.dispatchEvent(
      new CustomEvent(CATALOG_CACHE_UPDATED_EVENT, {
        detail: {
          cacheKey,
          payload: nextPayload,
        },
      }),
    );
  } catch {
    // Best-effort cache only.
  }
}
