import { deleteJson } from "@/shared/api/http-client";

export async function deleteGarageVehicle(token: string, vehicleId: string): Promise<void> {
  await deleteJson<void>(`/users/garage-vehicles/${vehicleId}/`, undefined, { token });
}

