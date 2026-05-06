"use client";

export const CATALOG_RETURN_STATE_KEY = "catalog:return-state:v1";
export const CATALOG_RETURN_STATE_TTL_MS = 10 * 60 * 1000;
export const CATALOG_LIST_SCROLL_MARGIN_PX = 12;

export type CatalogReturnState = {
  catalogUrl: string;
  productId: string;
  scrollY: number;
  productViewportTop: number;
  savedAt: number;
};

export function normalizeCatalogUrl(value: string): string {
  const [withoutHash] = value.split("#", 1);
  return withoutHash || "/";
}

export function getCurrentCatalogUrl(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return normalizeCatalogUrl(`${window.location.pathname}${window.location.search}`);
}

export function isCatalogReturnStateFresh(state: CatalogReturnState, now = Date.now()): boolean {
  return now - state.savedAt <= CATALOG_RETURN_STATE_TTL_MS;
}

export function saveCatalogReturnState(state: Omit<CatalogReturnState, "savedAt">): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    const nextState: CatalogReturnState = {
      ...state,
      catalogUrl: normalizeCatalogUrl(state.catalogUrl),
      scrollY: Math.max(0, Math.floor(state.scrollY)),
      productViewportTop: Math.floor(state.productViewportTop),
      savedAt: Date.now(),
    };
    window.sessionStorage.setItem(CATALOG_RETURN_STATE_KEY, JSON.stringify(nextState));
  } catch {
    // Best-effort navigation state only.
  }
}

export function readCatalogReturnState(now = Date.now()): CatalogReturnState | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(CATALOG_RETURN_STATE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as CatalogReturnState;
    if (
      !parsed
      || typeof parsed.catalogUrl !== "string"
      || typeof parsed.productId !== "string"
      || typeof parsed.scrollY !== "number"
      || typeof parsed.productViewportTop !== "number"
      || typeof parsed.savedAt !== "number"
    ) {
      window.sessionStorage.removeItem(CATALOG_RETURN_STATE_KEY);
      return null;
    }
    if (!isCatalogReturnStateFresh(parsed, now)) {
      window.sessionStorage.removeItem(CATALOG_RETURN_STATE_KEY);
      return null;
    }
    return {
      ...parsed,
      catalogUrl: normalizeCatalogUrl(parsed.catalogUrl),
    };
  } catch {
    return null;
  }
}

export function readMatchingCatalogReturnState(catalogUrl = getCurrentCatalogUrl()): CatalogReturnState | null {
  if (!catalogUrl) {
    return null;
  }
  const state = readCatalogReturnState();
  if (!state) {
    return null;
  }
  return normalizeCatalogUrl(state.catalogUrl) === normalizeCatalogUrl(catalogUrl) ? state : null;
}

export function clearCatalogReturnState(): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.sessionStorage.removeItem(CATALOG_RETURN_STATE_KEY);
  } catch {
    // Best-effort navigation state only.
  }
}

export function resolveCatalogListScrollY(sectionTopY: number, marginPx = CATALOG_LIST_SCROLL_MARGIN_PX): number {
  return Math.max(0, Math.floor(sectionTopY - marginPx));
}

export function resolveCatalogProductScrollY(params: {
  productDocumentTop: number;
  savedProductViewportTop: number;
  fallbackScrollY: number;
}): number {
  const restoredY = params.productDocumentTop - params.savedProductViewportTop;
  if (!Number.isFinite(restoredY) || restoredY < 0) {
    return Math.max(0, Math.floor(params.fallbackScrollY));
  }
  return Math.floor(restoredY);
}

export function scrollCatalogListToTop(section: HTMLElement | null): void {
  if (typeof window === "undefined") {
    return;
  }
  const sectionTopY = section ? section.getBoundingClientRect().top + window.scrollY : 0;
  window.scrollTo({ top: resolveCatalogListScrollY(sectionTopY), behavior: "auto" });
}

export function scrollCatalogPageToTop(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.scrollTo({ top: 0, behavior: "auto" });
}

export function restoreCatalogProductScroll(state: CatalogReturnState, productNode: HTMLElement | null): boolean {
  if (typeof window === "undefined" || !productNode) {
    return false;
  }
  const productDocumentTop = productNode.getBoundingClientRect().top + window.scrollY;
  window.scrollTo({
    top: resolveCatalogProductScrollY({
      productDocumentTop,
      savedProductViewportTop: state.productViewportTop,
      fallbackScrollY: state.scrollY,
    }),
    behavior: "auto",
  });
  return true;
}
