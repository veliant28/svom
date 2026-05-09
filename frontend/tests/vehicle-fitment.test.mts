import assert from "node:assert/strict";
import test from "node:test";

import { resolveActiveVehicleFitmentParams } from "../src/features/catalog/lib/vehicle-fitment.ts";

test("does not return fitment params for legacy garage selection", () => {
  assert.deepEqual(
    resolveActiveVehicleFitmentParams({
      activeVehicleSource: "garage",
      activeGarageVehicleId: "g-1",
      activeGarageVehicleCatalogSource: "legacy",
      activeGarageVehicleAutoDbPassangerCarId: null,
      activeTemporaryCarModificationId: null,
      activeTemporaryAutoDbPassangerCarId: null,
    }),
    {},
  );
});

test("returns vehicle_id for autodb garage selection", () => {
  assert.deepEqual(
    resolveActiveVehicleFitmentParams({
      activeVehicleSource: "garage",
      activeGarageVehicleId: "g-2",
      activeGarageVehicleCatalogSource: "autodb_pro",
      activeGarageVehicleAutoDbPassangerCarId: 4001,
      activeTemporaryCarModificationId: null,
      activeTemporaryAutoDbPassangerCarId: null,
    }),
    { vehicle_id: "4001", garage_vehicle: "g-2" },
  );
});

test("does not return fitment params for temporary legacy selection", () => {
  assert.deepEqual(
    resolveActiveVehicleFitmentParams({
      activeVehicleSource: "temporary",
      activeGarageVehicleId: null,
      activeGarageVehicleCatalogSource: null,
      activeGarageVehicleAutoDbPassangerCarId: null,
      activeTemporaryCarModificationId: 123,
      activeTemporaryAutoDbPassangerCarId: null,
    }),
    {},
  );
});

test("returns vehicle_id for temporary autodb selection", () => {
  assert.deepEqual(
    resolveActiveVehicleFitmentParams({
      activeVehicleSource: "temporary_autodb",
      activeGarageVehicleId: null,
      activeGarageVehicleCatalogSource: null,
      activeGarageVehicleAutoDbPassangerCarId: null,
      activeTemporaryCarModificationId: null,
      activeTemporaryAutoDbPassangerCarId: 901,
    }),
    { vehicle_id: "901" },
  );
});
