import { postJson } from "@/shared/api/http-client";

import type { GarageVehicle, GarageVehicleCreatePayload } from "@/features/garage/types/garage";

export async function createGarageVehicle(
  token: string,
  payload: GarageVehicleCreatePayload,
): Promise<GarageVehicle> {
  return postJson<GarageVehicle, GarageVehicleCreatePayload>("/users/garage-vehicles/", payload, undefined, { token });
}
