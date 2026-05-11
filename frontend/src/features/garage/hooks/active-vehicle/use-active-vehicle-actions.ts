import { useCallback } from "react";
import type { Dispatch, SetStateAction } from "react";

import { createGarageVehicle } from "@/features/garage/api/create-garage-vehicle";
import type { ActiveVehicleSource } from "@/features/garage/hooks/active-vehicle/active-vehicle-context";
import type { GarageVehicle, GarageVehicleCreatePayload } from "@/features/garage/types/garage";

type SourceSetter = Dispatch<SetStateAction<ActiveVehicleSource>>;
type StringSetter = Dispatch<SetStateAction<string | null>>;
type NumberSetter = Dispatch<SetStateAction<number | null>>;
type BoolSetter = Dispatch<SetStateAction<boolean>>;

export function useActiveVehicleActions({
  token,
  isAuthenticated,
  refreshGarageVehicles,
  setActiveVehicleSource,
  setActiveGarageVehicleId,
  setActiveTemporaryAutoDbPassangerCarId,
  setIsManualSelection,
}: {
  token: string | null;
  isAuthenticated: boolean;
  refreshGarageVehicles: () => Promise<GarageVehicle[]>;
  setActiveVehicleSource: SourceSetter;
  setActiveGarageVehicleId: StringSetter;
  setActiveTemporaryAutoDbPassangerCarId: NumberSetter;
  setIsManualSelection: BoolSetter;
}) {
  const selectGarageVehicle = useCallback((vehicleId: string, options?: { manual?: boolean }) => {
    setActiveVehicleSource("garage");
    setActiveGarageVehicleId(vehicleId);
    setActiveTemporaryAutoDbPassangerCarId(null);
    setIsManualSelection(options?.manual ?? true);
  }, [setActiveGarageVehicleId, setActiveTemporaryAutoDbPassangerCarId, setActiveVehicleSource, setIsManualSelection]);

  const selectTemporaryAutoDbVehicle = useCallback(
    (
      payload: { manufacturerId: number; modelId: number; passangerCarId: number },
      options?: { manual?: boolean },
    ) => {
      if (
        !Number.isInteger(payload.manufacturerId) ||
        !Number.isInteger(payload.modelId) ||
        !Number.isInteger(payload.passangerCarId) ||
        payload.manufacturerId <= 0 ||
        payload.modelId <= 0 ||
        payload.passangerCarId <= 0
      ) {
        return;
      }

      setActiveVehicleSource("temporary_autodb");
      setActiveTemporaryAutoDbPassangerCarId(payload.passangerCarId);
      setActiveGarageVehicleId(null);
      setIsManualSelection(options?.manual ?? true);
    },
    [
      setActiveGarageVehicleId,
      setActiveTemporaryAutoDbPassangerCarId,
      setActiveVehicleSource,
      setIsManualSelection,
    ],
  );

  const clearActiveVehicle = useCallback((options?: { manual?: boolean }) => {
    setActiveVehicleSource("none");
    setActiveGarageVehicleId(null);
    setActiveTemporaryAutoDbPassangerCarId(null);
    setIsManualSelection(options?.manual ?? true);
  }, [setActiveGarageVehicleId, setActiveTemporaryAutoDbPassangerCarId, setActiveVehicleSource, setIsManualSelection]);

  const addVehicleToGarage = useCallback(
    async (payload: GarageVehicleCreatePayload): Promise<GarageVehicle> => {
      if (!token || !isAuthenticated) {
        throw new Error("Authentication required");
      }

      const created = await createGarageVehicle(token, payload);
      await refreshGarageVehicles();
      return created;
    },
    [isAuthenticated, refreshGarageVehicles, token],
  );

  return {
    selectGarageVehicle,
    selectTemporaryAutoDbVehicle,
    clearActiveVehicle,
    addVehicleToGarage,
  };
}
