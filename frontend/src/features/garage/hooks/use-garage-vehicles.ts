"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { deleteGarageVehicle } from "@/features/garage/api/delete-garage-vehicle";
import { getGarageVehicles } from "@/features/garage/api/get-garage-vehicles";
import { updateGarageVehicle } from "@/features/garage/api/update-garage-vehicle";
import type { GarageVehicle } from "@/features/garage/types/garage";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

export function useGarageVehicles() {
  const { token, isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const tPage = useTranslations("garage.page");
  const tCard = useTranslations("garage.card");
  const { showApiError, showSuccess } = useStorefrontFeedback();
  const [garageVehicles, setGarageVehicles] = useState<GarageVehicle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionLoading, setIsActionLoading] = useState(false);

  const refreshGarageVehicles = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setGarageVehicles([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const data = await getGarageVehicles(token);
      setGarageVehicles(data);
    } catch (error) {
      setGarageVehicles([]);
      showApiError(error, tPage("states.error"));
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, showApiError, tPage, token]);

  const setPrimaryGarageVehicle = useCallback(
    async (vehicleId: string) => {
      if (!token || !isAuthenticated) {
        return;
      }

      setIsActionLoading(true);
      try {
        await updateGarageVehicle(token, vehicleId, { is_primary: true });
        await refreshGarageVehicles();
        showSuccess(tCard("messages.makePrimarySuccess"));
      } catch (error) {
        showApiError(error, tCard("messages.makePrimaryFailed"));
      } finally {
        setIsActionLoading(false);
      }
    },
    [isAuthenticated, refreshGarageVehicles, showApiError, showSuccess, tCard, token],
  );

  const removeGarageVehicle = useCallback(
    async (vehicleId: string) => {
      if (!token || !isAuthenticated) {
        return;
      }

      setIsActionLoading(true);
      try {
        await deleteGarageVehicle(token, vehicleId);
        await refreshGarageVehicles();
        showSuccess(tCard("messages.deleteSuccess"));
      } catch (error) {
        showApiError(error, tCard("messages.deleteFailed"));
      } finally {
        setIsActionLoading(false);
      }
    },
    [isAuthenticated, refreshGarageVehicles, showApiError, showSuccess, tCard, token],
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
    refreshGarageVehicles,
    setPrimaryGarageVehicle,
    removeGarageVehicle,
  };
}
