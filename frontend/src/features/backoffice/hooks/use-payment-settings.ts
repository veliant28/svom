"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getBackofficeMonobankSettings,
  testBackofficeMonobankConnection,
  updateBackofficeMonobankSettings,
} from "@/features/backoffice/api/payment-api";
import type { BackofficeMonobankConnectionCheck, BackofficeMonobankSettings } from "@/features/backoffice/types/payment.types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";

export function usePaymentSettings({ t }: { t: (key: string) => string }) {
  const { token } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();
  const [settings, setSettings] = useState<BackofficeMonobankSettings | null>(null);
  const [connectionCheck, setConnectionCheck] = useState<BackofficeMonobankConnectionCheck | null>(null);
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
      const payload = await getBackofficeMonobankSettings(token);
      setSettings(payload);
    } catch (error) {
      showApiError(error, t("payments.messages.loadSettingsFailed"));
    } finally {
      setIsLoading(false);
    }
  }, [showApiError, t, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = useCallback(
    async (payload: Partial<{ is_enabled: boolean; merchant_token: string; widget_key_id: string; widget_private_key: string }>) => {
      if (!token) {
        return null;
      }
      setIsSaving(true);
      try {
        const next = await updateBackofficeMonobankSettings(token, payload);
        setSettings(next);
        showSuccess(t("payments.messages.settingsSaved"));
        return next;
      } catch (error) {
        showApiError(error, t("payments.messages.saveSettingsFailed"));
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
      const result = await testBackofficeMonobankConnection(token);
      setConnectionCheck(result);
      if (result.ok) {
        showSuccess(t("payments.messages.connectionOk"));
      }
      await load();
      return result;
    } catch (error) {
      showApiError(error, t("payments.messages.connectionFailed"));
      return null;
    } finally {
      setIsTesting(false);
    }
  }, [load, showApiError, showSuccess, t, token]);

  return {
    settings,
    connectionCheck,
    isLoading,
    isSaving,
    isTesting,
    save,
    testConnection,
    reload: load,
  };
}
