export type VehicleFitmentParams = {
  garage_vehicle?: string;
  car_modification?: string;
};

export function resolveActiveVehicleFitmentParams(params: {
  activeVehicleSource: "none" | "garage" | "temporary" | "temporary_autodb";
  activeGarageVehicleId: string | null;
  activeGarageVehicleCatalogSource: "legacy" | "autodb_pro" | null;
  activeTemporaryCarModificationId: number | null;
}): VehicleFitmentParams {
  if (
    params.activeVehicleSource === "garage" &&
    params.activeGarageVehicleId &&
    params.activeGarageVehicleCatalogSource === "legacy"
  ) {
    return { garage_vehicle: params.activeGarageVehicleId };
  }

  if (params.activeVehicleSource === "temporary" && params.activeTemporaryCarModificationId) {
    return { car_modification: String(params.activeTemporaryCarModificationId) };
  }

  return {};
}
