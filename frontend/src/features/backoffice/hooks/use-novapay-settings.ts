"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getBackofficeNovaPaySettings,
  testBackofficeNovaPayConnection,
  updateBackofficeNovaPaySettings,
} from "@/features/backoffice/api/payment-api";
import type { BackofficeNovaPaySettings } from "@/features/backoffice/types/payment.types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";

export function useNovaPaySettings({ t }: { t: (key: string) => string }) {
  const { token } = useAuth();
  const { showApiError, showSuccess, showWarning } = useBackofficeFeedback();
  const [settings, setSettings] = useState<BackofficeNovaPaySettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  const load = useCallback(async () => {
    if (!token) {
      setIsLoading(false);
      setSettings(null);
      return;
    }

    setIsLoading(true);
    try {
      const payload = await getBackofficeNovaPaySettings(token);
      setSettings(payload);
    } catch (error) {
      showApiError(error, t("payments.messages.loadNovaSettingsFailed"));
    } finally {
      setIsLoading(false);
    }
  }, [showApiError, t, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = useCallback(
    async (payload: Partial<{ is_enabled: boolean; merchant_id: string; api_token: string }>) => {
      if (!token) {
        return null;
      }
      setIsSaving(true);
      try {
        const next = await updateBackofficeNovaPaySettings(token, payload);
        setSettings(next);
        showSuccess(t("payments.messages.novaSettingsSaved"));
        return next;
      } catch (error) {
        showApiError(error, t("payments.messages.saveNovaSettingsFailed"));
        return null;
      } finally {
        setIsSaving(false);
      }
    },
    [showApiError, showSuccess, t, token],
  );

  const testConnection = useCallback(async () => {
    if (!token) {
      return null;
    }
    setIsTesting(true);
    try {
      const result = await testBackofficeNovaPayConnection(token);
      if (result.ok) {
        showSuccess(t("payments.messages.novaConnectionOk"));
      } else {
        showWarning(result.message || t("payments.messages.novaConnectionFailed"));
      }
      await load();
      return result;
    } catch (error) {
      showApiError(error, t("payments.messages.novaConnectionFailed"));
      return null;
    } finally {
      setIsTesting(false);
    }
  }, [load, showApiError, showSuccess, showWarning, t, token]);

  return {
    settings,
    isLoading,
    isSaving,
    isTesting,
    save,
    testConnection,
    reload: load,
  };
}
