import assert from "node:assert/strict";
import test from "node:test";

import {
  CATALOG_RETURN_STATE_TTL_MS,
  isCatalogReturnStateFresh,
  normalizeCatalogUrl,
  resolveCatalogListScrollY,
  resolveCatalogProductScrollY,
  type CatalogReturnState,
} from "../src/features/catalog/lib/catalog-navigation-state.ts";

function makeState(savedAt: number): CatalogReturnState {
  return {
    catalogUrl: "/uk/catalog?category_id=1",
    productId: "product-1",
    scrollY: 820,
    productViewportTop: 240,
    savedAt,
  };
}

test("normalizes catalog URLs without hash fragments", () => {
  assert.equal(normalizeCatalogUrl("/uk/catalog?category_id=1#product-1"), "/uk/catalog?category_id=1");
  assert.equal(normalizeCatalogUrl("#product-1"), "/");
});

test("catalog return state expires by TTL", () => {
  const now = 1_000_000;

  assert.equal(isCatalogReturnStateFresh(makeState(now - CATALOG_RETURN_STATE_TTL_MS + 1), now), true);
  assert.equal(isCatalogReturnStateFresh(makeState(now - CATALOG_RETURN_STATE_TTL_MS - 1), now), false);
});

test("catalog list scroll target starts at section top with margin", () => {
  assert.equal(resolveCatalogListScrollY(240, 12), 228);
  assert.equal(resolveCatalogListScrollY(8, 12), 0);
});

test("product restore preserves previous product viewport position", () => {
  assert.equal(
    resolveCatalogProductScrollY({
      productDocumentTop: 1200,
      savedProductViewportTop: 260,
      fallbackScrollY: 900,
    }),
    940,
  );
});

test("product restore falls back to saved scroll for invalid target", () => {
  assert.equal(
    resolveCatalogProductScrollY({
      productDocumentTop: Number.NaN,
      savedProductViewportTop: 260,
      fallbackScrollY: 900,
    }),
    900,
  );
});
