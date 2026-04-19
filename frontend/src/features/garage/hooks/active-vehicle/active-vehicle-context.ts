import { createContext } from "react";

import type { GarageVehicle, GarageVehicleCreatePayload } from "@/features/garage/types/garage";

export type ActiveVehicleSource = "none" | "garage" | "temporary";

export type ActiveVehicleContextValue = {
  garageVehicles: GarageVehicle[];
  isGarageLoading: boolean;
  garageError: string | null;
  refreshGarageVehicles: () => Promise<GarageVehicle[]>;
  addVehicleToGarage: (payload: GarageVehicleCreatePayload) => Promise<GarageVehicle>;
  activeVehicleSource: ActiveVehicleSource;
  activeGarageVehicleId: string | null;
  activeTemporaryCarModificationId: number | null;
  activeGarageVehicle: GarageVehicle | null;
  isVehicleFilterActive: boolean;
  isManualSelection: boolean;
  selectGarageVehicle: (vehicleId: string, options?: { manual?: boolean }) => void;
  selectTemporaryVehicle: (carModificationId: number, options?: { manual?: boolean }) => void;
  clearActiveVehicle: (options?: { manual?: boolean }) => void;
};

export const ActiveVehicleContext = createContext<ActiveVehicleContextValue | null>(null);
