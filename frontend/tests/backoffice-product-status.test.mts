import test from "node:test";
import assert from "node:assert/strict";

import {
  formatWarehouseSummaryLabel,
  resolveProductPriceStatusLabel,
  resolveProductPriceStatusTone,
} from "../src/features/backoffice/lib/products/product-status.ts";

test("resolveProductPriceStatusTone maps known statuses", () => {
  assert.equal(resolveProductPriceStatusTone("has_price"), "success");
  assert.equal(resolveProductPriceStatusTone("no_product_price"), "warning");
  assert.equal(resolveProductPriceStatusTone("invalid_offer"), "error");
  assert.equal(resolveProductPriceStatusTone("no_available_offer"), "gray");
});

test("resolveProductPriceStatusLabel returns stable fallback", () => {
  assert.equal(resolveProductPriceStatusLabel("has_price"), "has_price");
  assert.equal(resolveProductPriceStatusLabel("no_product_price"), "no_product_price");
  assert.equal(resolveProductPriceStatusLabel("invalid_offer"), "invalid_offer");
  assert.equal(resolveProductPriceStatusLabel("no_available_offer"), "no_available_offer");
});

test("formatWarehouseSummaryLabel includes zero warehouses in total", () => {
  assert.equal(
    formatWarehouseSummaryLabel({
      warehouse_total_count: 15,
      warehouse_nonzero_count: 4,
      stock_qty_total: 41,
      supplier_offer_stock_sum: 30,
    }),
    "4/15 складів",
  );
  assert.equal(formatWarehouseSummaryLabel(undefined), "-");
});
