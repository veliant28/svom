import assert from "node:assert/strict";
import test from "node:test";

import { normalizeDisplayText } from "../src/features/garage/lib/clean-text.ts";
import { isTruthyFlag } from "../src/features/garage/config/vehicle-catalog.ts";
import { isModelSelectorDisabled, isVehicleTableReady } from "../src/features/backoffice/lib/autodb-vehicle-catalog.ts";

test("normalizeDisplayText removes line breaks and extra spaces", () => {
  assert.equal(normalizeDisplayText("  MAZDA\nXEDOS 6\t2.0 V6  "), "MAZDA XEDOS 6 2.0 V6");
});

test("isTruthyFlag recognizes enabled values", () => {
  assert.equal(isTruthyFlag("1"), true);
  assert.equal(isTruthyFlag("true"), true);
  assert.equal(isTruthyFlag("yes"), true);
  assert.equal(isTruthyFlag("on"), true);
});

test("isTruthyFlag rejects disabled values", () => {
  assert.equal(isTruthyFlag("0"), false);
  assert.equal(isTruthyFlag("false"), false);
  assert.equal(isTruthyFlag(undefined), false);
});

test("model selector disabled until manufacturer selected", () => {
  assert.equal(isModelSelectorDisabled(""), true);
  assert.equal(isModelSelectorDisabled("72"), false);
});

test("vehicle table becomes ready only after make and model are selected", () => {
  assert.equal(isVehicleTableReady("", ""), false);
  assert.equal(isVehicleTableReady("72", ""), false);
  assert.equal(isVehicleTableReady("72", "82"), true);
});
