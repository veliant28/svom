import assert from "node:assert/strict";
import test from "node:test";

import { resolveGplPriceLevelMeta, resolveGplWarehouseLabel } from "../src/features/backoffice/lib/gpl-field-labels.ts";

test("maps GPL price_type keys to readable wholesale labels", () => {
  assert.equal(resolveGplPriceLevelMeta("price_type_1")?.badgeLabel, "ОПТ2");
  assert.equal(resolveGplPriceLevelMeta("price_type_2")?.badgeLabel, "ОПТ4");
  assert.equal(resolveGplPriceLevelMeta("price_type_9")?.badgeLabel, "ОПТ10");
  assert.equal(resolveGplPriceLevelMeta("price_type_10")?.badgeLabel, "РРЦ");
});

test("maps GPL warehouse keys to readable names", () => {
  assert.equal(resolveGplWarehouseLabel("count_warehouse_1"), "Склад ПЛТВ");
  assert.equal(resolveGplWarehouseLabel("count_warehouse_2"), "Склад ТРНП");
  assert.equal(resolveGplWarehouseLabel("count_warehouse_4"), "Склад БРСП");
});
