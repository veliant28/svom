"use client";

import { useContext, useMemo, useState } from "react";

import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  ActiveVehicleContext,
  type ActiveVehicleContextValue,
  type ActiveVehicleSource,
} from "@/features/garage/hooks/active-vehicle/active-vehicle-context";
import { useActiveVehicleActions } from "@/features/garage/hooks/active-vehicle/use-active-vehicle-actions";
import { useActiveVehicleDerivedState } from "@/features/garage/hooks/active-vehicle/use-active-vehicle-derived-state";
import { useActiveVehicleStorage } from "@/features/garage/hooks/active-vehicle/use-active-vehicle-storage";
import { useActiveVehicleSync } from "@/features/garage/hooks/active-vehicle/use-active-vehicle-sync";

export function ActiveVehicleProvider({ children }: { children: React.ReactNode }) {
  const { token, isAuthenticated, isLoading: isAuthLoading } = useAuth();

  const [activeVehicleSource, setActiveVehicleSource] = useState<ActiveVehicleSource>("none");
  const [activeGarageVehicleId, setActiveGarageVehicleId] = useState<string | null>(null);
  const [activeTemporaryCarModificationId, setActiveTemporaryCarModificationId] = useState<number | null>(null);
  const [isManualSelection, setIsManualSelection] = useState(false);

  const { hasHydratedFromStorage } = useActiveVehicleStorage({
    activeVehicleSource,
    activeGarageVehicleId,
    activeTemporaryCarModificationId,
    isManualSelection,
    setActiveVehicleSource,
    setActiveGarageVehicleId,
    setActiveTemporaryCarModificationId,
    setIsManualSelection,
  });

  const { garageVehicles, isGarageLoading, garageError, refreshGarageVehicles } = useActiveVehicleSync({
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
  });

  const { selectGarageVehicle, selectTemporaryVehicle, clearActiveVehicle, addVehicleToGarage } = useActiveVehicleActions({
    token,
    isAuthenticated,
    refreshGarageVehicles,
    setActiveVehicleSource,
    setActiveGarageVehicleId,
    setActiveTemporaryCarModificationId,
    setIsManualSelection,
  });

  const { activeGarageVehicle, isVehicleFilterActive } = useActiveVehicleDerivedState({
    garageVehicles,
    activeGarageVehicleId,
    activeVehicleSource,
  });

  const value = useMemo<ActiveVehicleContextValue>(
    () => ({
      garageVehicles,
      isGarageLoading,
      garageError,
      refreshGarageVehicles,
      addVehicleToGarage,
      activeVehicleSource,
      activeGarageVehicleId,
      activeTemporaryCarModificationId,
      activeGarageVehicle,
      isVehicleFilterActive,
      isManualSelection,
      selectGarageVehicle,
      selectTemporaryVehicle,
      clearActiveVehicle,
    }),
    [
      activeGarageVehicle,
      activeGarageVehicleId,
      activeTemporaryCarModificationId,
      activeVehicleSource,
      addVehicleToGarage,
      clearActiveVehicle,
      garageError,
      garageVehicles,
      isGarageLoading,
      isManualSelection,
      isVehicleFilterActive,
      refreshGarageVehicles,
      selectGarageVehicle,
      selectTemporaryVehicle,
    ],
  );

  return <ActiveVehicleContext.Provider value={value}>{children}</ActiveVehicleContext.Provider>;
}

export function useActiveVehicle() {
  const context = useContext(ActiveVehicleContext);
  if (!context) {
    throw new Error("useActiveVehicle must be used within ActiveVehicleProvider");
  }
  return context;
}
