import { getJson } from "@/shared/api/http-client";
import { normalizeListResponse, type ListResponse } from "@/shared/api/normalize-list-response";

import type { GarageVehicle } from "@/features/garage/types/garage";

type GarageVehiclesResponse = ListResponse<GarageVehicle>;

export function normalizeGarageVehiclesResponse(data: GarageVehiclesResponse): GarageVehicle[] {
  return normalizeListResponse(data);
}

export async function getGarageVehicles(token: string): Promise<GarageVehicle[]> {
  const data = await getJson<GarageVehiclesResponse>("/users/garage-vehicles/", undefined, { token });

  return normalizeGarageVehiclesResponse(data);
}
