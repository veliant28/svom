"use client";

import { useCallback, useEffect, useState } from "react";

import { getBackofficeLiqPaySettings, updateBackofficeLiqPaySettings } from "@/features/backoffice/api/payment-api";
import type { BackofficeLiqPaySettings } from "@/features/backoffice/types/payment.types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";

export function useLiqPaySettings({ t }: { t: (key: string) => string }) {
  const { token } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();
  const [settings, setSettings] = useState<BackofficeLiqPaySettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const load = useCallback(async () => {
    if (!token) {
      setIsLoading(false);
      setSettings(null);
      return;
    }

    setIsLoading(true);
    try {
      const payload = await getBackofficeLiqPaySettings(token);
      setSettings(payload);
    } catch (error) {
      showApiError(error, t("payments.messages.loadLiqpaySettingsFailed"));
    } finally {
      setIsLoading(false);
    }
  }, [showApiError, t, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = useCallback(
    async (payload: Partial<{ is_enabled: boolean; public_key: string; private_key: string }>) => {
      if (!token) {
        return null;
      }
      setIsSaving(true);
      try {
        const next = await updateBackofficeLiqPaySettings(token, payload);
        setSettings(next);
        showSuccess(t("payments.messages.liqpaySettingsSaved"));
        return next;
      } catch (error) {
        showApiError(error, t("payments.messages.saveLiqpaySettingsFailed"));
        return null;
      } finally {
        setIsSaving(false);
      }
    },
    [showApiError, showSuccess, t, token],
  );

  return {
    settings,
    isLoading,
    isSaving,
    save,
    reload: load,
  };
}
