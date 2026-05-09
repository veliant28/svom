import assert from "node:assert/strict";
import test from "node:test";

import { resolveCompatibilityBadgeState } from "../src/features/catalog/lib/compatibility-badge.ts";

test("shows fits badge when selected vehicle is compatible", () => {
  assert.equal(
    resolveCompatibilityBadgeState({
      fitsSelectedVehicle: true,
      hasFitmentData: true,
      isAutoDbCompatibleDataAvailable: true,
    }),
    "fits",
  );
});

test("shows not_fits badge when selected vehicle is incompatible", () => {
  assert.equal(
    resolveCompatibilityBadgeState({
      fitsSelectedVehicle: false,
      hasFitmentData: true,
      isAutoDbCompatibleDataAvailable: true,
    }),
    "not_fits",
  );
});

test("suppresses not_fits badge for show_all_with_badges categories without fitment data", () => {
  assert.equal(
    resolveCompatibilityBadgeState({
      fitsSelectedVehicle: false,
      hasFitmentData: false,
      isAutoDbCompatibleDataAvailable: false,
      suppressIncompatibleBadge: true,
    }),
    "none",
  );
});

test("keeps has_data badge for show_all_with_badges categories with safe fitment data", () => {
  assert.equal(
    resolveCompatibilityBadgeState({
      fitsSelectedVehicle: false,
      hasFitmentData: true,
      isAutoDbCompatibleDataAvailable: true,
      suppressIncompatibleBadge: true,
    }),
    "has_data",
  );
});

test("shows has_data badge when no vehicle selected but compatibility exists", () => {
  assert.equal(
    resolveCompatibilityBadgeState({
      fitsSelectedVehicle: null,
      hasFitmentData: true,
      isAutoDbCompatibleDataAvailable: false,
    }),
    "has_data",
  );
});

test("returns none when compatibility data absent", () => {
  assert.equal(
    resolveCompatibilityBadgeState({
      fitsSelectedVehicle: null,
      hasFitmentData: false,
      isAutoDbCompatibleDataAvailable: false,
    }),
    "none",
  );
});
