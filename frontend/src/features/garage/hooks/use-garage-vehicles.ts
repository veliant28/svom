"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { deleteGarageVehicle } from "@/features/garage/api/delete-garage-vehicle";
import { getGarageVehicles } from "@/features/garage/api/get-garage-vehicles";
import { updateGarageVehicle } from "@/features/garage/api/update-garage-vehicle";
import type { GarageVehicle } from "@/features/garage/types/garage";

type GarageVehiclesErrorCode = "load_failed" | "action_failed" | null;

export function useGarageVehicles() {
  const { token, isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const [garageVehicles, setGarageVehicles] = useState<GarageVehicle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [error, setError] = useState<GarageVehiclesErrorCode>(null);

  const refreshGarageVehicles = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setGarageVehicles([]);
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const data = await getGarageVehicles(token);
      setGarageVehicles(data);
    } catch {
      setGarageVehicles([]);
      setError("load_failed");
    } finally {
      setIsLoading(false);
    }
  }, [token, isAuthenticated]);

  const setPrimaryGarageVehicle = useCallback(
    async (vehicleId: string) => {
      if (!token || !isAuthenticated) {
        return;
      }

      setIsActionLoading(true);
      setError(null);
      try {
        await updateGarageVehicle(token, vehicleId, { is_primary: true });
        await refreshGarageVehicles();
      } catch {
        setError("action_failed");
      } finally {
        setIsActionLoading(false);
      }
    },
    [token, isAuthenticated, refreshGarageVehicles],
  );

  const removeGarageVehicle = useCallback(
    async (vehicleId: string) => {
      if (!token || !isAuthenticated) {
        return;
      }

      setIsActionLoading(true);
      setError(null);
      try {
        await deleteGarageVehicle(token, vehicleId);
        await refreshGarageVehicles();
      } catch {
        setError("action_failed");
      } finally {
        setIsActionLoading(false);
      }
    },
    [token, isAuthenticated, refreshGarageVehicles],
  );

  useEffect(() => {
    if (isAuthLoading) {
      return;
    }
    void refreshGarageVehicles();
  }, [isAuthLoading, refreshGarageVehicles]);

  return {
    garageVehicles,
    isLoading: isLoading || isAuthLoading,
    isActionLoading,
    error,
    refreshGarageVehicles,
    setPrimaryGarageVehicle,
    removeGarageVehicle,
  };
}
