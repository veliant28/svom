import assert from "node:assert/strict";
import test from "node:test";

import { buildProductIdentityParts } from "../src/features/catalog/lib/product-identity.ts";

test("includes sku, brand, and manufacturer article", () => {
  assert.deepEqual(
    buildProductIdentityParts({
      sku: "000000000024868",
      brandName: "BRISK",
      manufacturerArticle: "1462",
    }),
    ["000000000024868", "BRISK", "1462"],
  );
});

test("does not duplicate manufacturer article when equal to sku", () => {
  assert.deepEqual(
    buildProductIdentityParts({
      sku: "000000000024868",
      brandName: "BRISK",
      manufacturerArticle: "000000000024868",
    }),
    ["000000000024868", "BRISK"],
  );
});

test("does not include empty segments", () => {
  assert.deepEqual(
    buildProductIdentityParts({
      sku: "0001",
      brandName: "",
      manufacturerArticle: "",
    }),
    ["0001"],
  );
});
