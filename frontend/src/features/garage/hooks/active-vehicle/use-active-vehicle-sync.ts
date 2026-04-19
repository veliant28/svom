import { useCallback, useEffect, useRef, useState } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";

import { getGarageVehicles } from "@/features/garage/api/get-garage-vehicles";
import type { ActiveVehicleSource } from "@/features/garage/hooks/active-vehicle/active-vehicle-context";
import type { GarageVehicle } from "@/features/garage/types/garage";

type SourceSetter = Dispatch<SetStateAction<ActiveVehicleSource>>;
type StringSetter = Dispatch<SetStateAction<string | null>>;
type NumberSetter = Dispatch<SetStateAction<number | null>>;
type BoolSetter = Dispatch<SetStateAction<boolean>>;

export function useActiveVehicleSync({
  token,
  isAuthenticated,
  isAuthLoading,
  hasHydratedFromStorage,
  activeVehicleSource,
  activeGarageVehicleId,
  activeTemporaryCarModificationId,
  isManualSelection,
  setActiveVehicleSource,
  setActiveGarageVehicleId,
  setActiveTemporaryCarModificationId,
  setIsManualSelection,
}: {
  token: string | null;
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  hasHydratedFromStorage: MutableRefObject<boolean>;
  activeVehicleSource: ActiveVehicleSource;
  activeGarageVehicleId: string | null;
  activeTemporaryCarModificationId: number | null;
  isManualSelection: boolean;
  setActiveVehicleSource: SourceSetter;
  setActiveGarageVehicleId: StringSetter;
  setActiveTemporaryCarModificationId: NumberSetter;
  setIsManualSelection: BoolSetter;
}) {
  const [garageVehicles, setGarageVehicles] = useState<GarageVehicle[]>([]);
  const [isGarageLoading, setIsGarageLoading] = useState(true);
  const [garageError, setGarageError] = useState<string | null>(null);

  const wasAuthenticatedRef = useRef(false);
  const hasInitializedAuthStateRef = useRef(false);

  const refreshGarageVehicles = useCallback(async (): Promise<GarageVehicle[]> => {
    if (!token || !isAuthenticated) {
      setGarageVehicles([]);
      setGarageError(null);
      setIsGarageLoading(false);
      return [];
    }

    setIsGarageLoading(true);
    setGarageError(null);
    try {
      const data = await getGarageVehicles(token);
      setGarageVehicles(data);
      return data;
    } catch {
      setGarageVehicles([]);
      setGarageError("load_failed");
      return [];
    } finally {
      setIsGarageLoading(false);
    }
  }, [isAuthenticated, token]);

  useEffect(() => {
    if (isAuthLoading) {
      return;
    }
    void refreshGarageVehicles();
  }, [isAuthLoading, refreshGarageVehicles]);

  useEffect(() => {
    if (isAuthLoading) {
      return;
    }

    if (!hasInitializedAuthStateRef.current) {
      // Treat auth restored from persisted token as baseline.
      // Reset to primary only after an actual logout -> login transition.
      wasAuthenticatedRef.current = isAuthenticated;
      hasInitializedAuthStateRef.current = true;
      return;
    }

    const wasAuthenticated = wasAuthenticatedRef.current;
    if (!wasAuthenticated && isAuthenticated) {
      // After sign-in, start from primary vehicle by default.
      // User can switch to another vehicle manually afterwards.
      setActiveVehicleSource("none");
      setActiveGarageVehicleId(null);
      setActiveTemporaryCarModificationId(null);
      setIsManualSelection(false);
    }

    wasAuthenticatedRef.current = isAuthenticated;
  }, [isAuthenticated, isAuthLoading, setActiveGarageVehicleId, setActiveTemporaryCarModificationId, setActiveVehicleSource, setIsManualSelection]);

  useEffect(() => {
    if (!hasHydratedFromStorage.current || isAuthLoading) {
      return;
    }

    if (!isAuthenticated) {
      if (activeVehicleSource !== "temporary") {
        setActiveVehicleSource("none");
        setActiveGarageVehicleId(null);
        setActiveTemporaryCarModificationId(null);
        setIsManualSelection(false);
      }
      return;
    }

    const primaryVehicle = garageVehicles.find((vehicle) => vehicle.is_primary) ?? null;
    const hasSelectedGarageVehicle =
      activeVehicleSource === "garage" &&
      Boolean(activeGarageVehicleId) &&
      garageVehicles.some((vehicle) => vehicle.id === activeGarageVehicleId);

    if (isManualSelection) {
      if (activeVehicleSource === "garage" && !hasSelectedGarageVehicle) {
        if (primaryVehicle) {
          setActiveVehicleSource("garage");
          setActiveGarageVehicleId(primaryVehicle.id);
          setActiveTemporaryCarModificationId(null);
        } else {
          setActiveVehicleSource("none");
          setActiveGarageVehicleId(null);
        }
        setIsManualSelection(false);
      }
      return;
    }

    if (primaryVehicle) {
      if (activeVehicleSource !== "garage" || activeGarageVehicleId !== primaryVehicle.id) {
        setActiveVehicleSource("garage");
        setActiveGarageVehicleId(primaryVehicle.id);
        setActiveTemporaryCarModificationId(null);
      }
      return;
    }

    if (activeVehicleSource !== "none" || activeGarageVehicleId !== null || activeTemporaryCarModificationId !== null) {
      setActiveVehicleSource("none");
      setActiveGarageVehicleId(null);
      setActiveTemporaryCarModificationId(null);
    }
  }, [
    activeGarageVehicleId,
    activeTemporaryCarModificationId,
    activeVehicleSource,
    garageVehicles,
    hasHydratedFromStorage,
    isAuthenticated,
    isAuthLoading,
    isManualSelection,
    setActiveGarageVehicleId,
    setActiveTemporaryCarModificationId,
    setActiveVehicleSource,
    setIsManualSelection,
  ]);

  return {
    garageVehicles,
    isGarageLoading,
    garageError,
    refreshGarageVehicles,
  };
}
