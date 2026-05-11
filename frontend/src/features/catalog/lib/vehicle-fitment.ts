export type VehicleFitmentParams = {
  vehicle_id?: string;
  passanger_car_id?: string;
  garage_vehicle?: string;
};

export function resolveActiveVehicleFitmentParams(params: {
  activeVehicleSource: "none" | "garage" | "temporary_autodb";
  activeGarageVehicleId: string | null;
  activeGarageVehicleCatalogSource: "autodb_pro" | null;
  activeGarageVehicleAutoDbPassangerCarId: number | null;
  activeTemporaryAutoDbPassangerCarId: number | null;
}): VehicleFitmentParams {
  if (
    params.activeVehicleSource === "garage" &&
    params.activeGarageVehicleCatalogSource === "autodb_pro" &&
    params.activeGarageVehicleAutoDbPassangerCarId &&
    params.activeGarageVehicleAutoDbPassangerCarId > 0
  ) {
    return {
      vehicle_id: String(params.activeGarageVehicleAutoDbPassangerCarId),
      garage_vehicle: params.activeGarageVehicleId || undefined,
    };
  }

  if (
    params.activeVehicleSource === "temporary_autodb" &&
    params.activeTemporaryAutoDbPassangerCarId &&
    params.activeTemporaryAutoDbPassangerCarId > 0
  ) {
    return { vehicle_id: String(params.activeTemporaryAutoDbPassangerCarId) };
  }

  return {};
}
