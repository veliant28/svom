"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  getBackofficeFooterSettings,
  updateBackofficeFooterSettings,
} from "@/features/backoffice/api/footer-settings-api";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import type { BackofficeFooterSettings } from "@/features/backoffice/types/footer-settings.types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  FOOTER_SETTINGS_UPDATED_AT_KEY,
  FOOTER_SETTINGS_UPDATED_EVENT,
} from "@/shared/lib/footer-settings-sync";

export function useFooterSettings({ t }: { t: (key: string) => string }) {
  const { token } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();
  const tRef = useRef(t);
  const showApiErrorRef = useRef(showApiError);

  const [settings, setSettings] = useState<BackofficeFooterSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    tRef.current = t;
  }, [t]);

  useEffect(() => {
    showApiErrorRef.current = showApiError;
  }, [showApiError]);

  const load = useCallback(async () => {
    if (!token) {
      setSettings(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const payload = await getBackofficeFooterSettings(token);
      setSettings(payload);
    } catch (error) {
      showApiErrorRef.current(error, tRef.current("footerSettings.messages.loadFailed"));
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = useCallback(
    async (payload: Partial<BackofficeFooterSettings>) => {
      if (!token) {
        return null;
      }
      setIsSaving(true);
      try {
        const next = await updateBackofficeFooterSettings(token, payload);
        setSettings(next);
        showSuccess(t("footerSettings.messages.saved"));
        if (typeof window !== "undefined") {
          window.localStorage.setItem(FOOTER_SETTINGS_UPDATED_AT_KEY, String(Date.now()));
          window.dispatchEvent(new CustomEvent(FOOTER_SETTINGS_UPDATED_EVENT));
        }
        return next;
      } catch (error) {
        showApiError(error, t("footerSettings.messages.saveFailed"));
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

export { FOOTER_SETTINGS_UPDATED_AT_KEY };
