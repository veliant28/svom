import assert from "node:assert/strict";
import test from "node:test";

import { resolveActiveVehicleFitmentParams } from "../src/features/catalog/lib/vehicle-fitment.ts";

test("returns legacy garage vehicle fitment params", () => {
  assert.deepEqual(
    resolveActiveVehicleFitmentParams({
      activeVehicleSource: "garage",
      activeGarageVehicleId: "g-1",
      activeGarageVehicleCatalogSource: "legacy",
      activeTemporaryCarModificationId: null,
    }),
    { garage_vehicle: "g-1" },
  );
});

test("does not return fitment params for autodb garage selection", () => {
  assert.deepEqual(
    resolveActiveVehicleFitmentParams({
      activeVehicleSource: "garage",
      activeGarageVehicleId: "g-2",
      activeGarageVehicleCatalogSource: "autodb_pro",
      activeTemporaryCarModificationId: null,
    }),
    {},
  );
});

test("returns temporary legacy car_modification fitment params", () => {
  assert.deepEqual(
    resolveActiveVehicleFitmentParams({
      activeVehicleSource: "temporary",
      activeGarageVehicleId: null,
      activeGarageVehicleCatalogSource: null,
      activeTemporaryCarModificationId: 123,
    }),
    { car_modification: "123" },
  );
});

test("does not return fitment params for temporary autodb selection", () => {
  assert.deepEqual(
    resolveActiveVehicleFitmentParams({
      activeVehicleSource: "temporary_autodb",
      activeGarageVehicleId: null,
      activeGarageVehicleCatalogSource: null,
      activeTemporaryCarModificationId: null,
    }),
    {},
  );
});
