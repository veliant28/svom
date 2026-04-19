import { useMemo } from "react";

import type { ActiveVehicleSource } from "@/features/garage/hooks/active-vehicle/active-vehicle-context";
import type { GarageVehicle } from "@/features/garage/types/garage";

export function useActiveVehicleDerivedState({
  garageVehicles,
  activeGarageVehicleId,
  activeVehicleSource,
}: {
  garageVehicles: GarageVehicle[];
  activeGarageVehicleId: string | null;
  activeVehicleSource: ActiveVehicleSource;
}) {
  const activeGarageVehicle = useMemo(
    () => garageVehicles.find((vehicle) => vehicle.id === activeGarageVehicleId) ?? null,
    [garageVehicles, activeGarageVehicleId],
  );

  const isVehicleFilterActive = activeVehicleSource !== "none";

  return {
    activeGarageVehicle,
    isVehicleFilterActive,
  };
}
