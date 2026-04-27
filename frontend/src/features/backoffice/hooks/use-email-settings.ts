"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getBackofficeEmailSettings,
  testBackofficeEmailSettings,
  updateBackofficeEmailSettings,
} from "@/features/backoffice/api/email-settings-api";
import type {
  BackofficeEmailSettings,
  BackofficeEmailSettingsPayload,
} from "@/features/backoffice/types/email-settings.types";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useAuth } from "@/features/auth/hooks/use-auth";

export function useEmailSettings({ t }: { t: (key: string) => string }) {
  const { token } = useAuth();
  const { showApiError, showSuccess, showWarning } = useBackofficeFeedback();
  const [settings, setSettings] = useState<BackofficeEmailSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  const load = useCallback(async () => {
    if (!token) {
      setSettings(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      setSettings(await getBackofficeEmailSettings(token));
    } catch (error) {
      showApiError(error, t("email.messages.loadFailed"));
    } finally {
      setIsLoading(false);
    }
  }, [showApiError, t, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = useCallback(
    async (payload: BackofficeEmailSettingsPayload) => {
      if (!token) {
        return null;
      }

      setIsSaving(true);
      try {
        const next = await updateBackofficeEmailSettings(token, payload);
        setSettings(next);
        showSuccess(t("email.messages.saved"));
        return next;
      } catch (error) {
        showApiError(error, t("email.messages.saveFailed"));
        return null;
      } finally {
        setIsSaving(false);
      }
    },
    [showApiError, showSuccess, t, token],
  );

  const test = useCallback(
    async (recipient: string) => {
      if (!token) {
        return null;
      }

      setIsTesting(true);
      try {
        const result = await testBackofficeEmailSettings(token, recipient);
        if (result.ok) {
          showSuccess(t("email.messages.testOk"));
        } else {
          showWarning(result.message || t("email.messages.testFailed"));
        }
        await load();
        return result;
      } catch (error) {
        showApiError(error, t("email.messages.testFailed"));
        return null;
      } finally {
        setIsTesting(false);
      }
    },
    [load, showApiError, showSuccess, showWarning, t, token],
  );

  return {
    settings,
    isLoading,
    isSaving,
    isTesting,
    reload: load,
    save,
    test,
  };
}
