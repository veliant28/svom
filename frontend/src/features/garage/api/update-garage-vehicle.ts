import { patchJson } from "@/shared/api/http-client";

import type { GarageVehicle, GarageVehicleUpdatePayload } from "@/features/garage/types/garage";

export async function updateGarageVehicle(
  token: string,
  vehicleId: string,
  payload: GarageVehicleUpdatePayload,
): Promise<GarageVehicle> {
  return patchJson<GarageVehicle, GarageVehicleUpdatePayload>(
    `/users/garage-vehicles/${vehicleId}/`,
    payload,
    undefined,
    { token },
  );
}

