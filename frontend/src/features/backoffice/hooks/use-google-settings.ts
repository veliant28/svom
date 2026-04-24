"use client";

import { useCallback, useEffect, useState } from "react";

import { getBackofficeGoogleSettings, updateBackofficeGoogleSettings } from "@/features/backoffice/api/seo-api";
import type { BackofficeGoogleEventSetting, BackofficeGoogleSettings } from "@/features/backoffice/api/seo-api.types";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { isApiRequestError } from "@/shared/api/http-client";

export function useGoogleSettings({ t }: { t: (key: string, values?: Record<string, string | number | Date>) => string }) {
  const { token } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const [settings, setSettings] = useState<BackofficeGoogleSettings | null>(null);
  const [events, setEvents] = useState<BackofficeGoogleEventSetting[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [activeEventId, setActiveEventId] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<"ga4_measurement_id" | "gtm_container_id", string>>>({});

  const load = useCallback(async () => {
    if (!token) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setLoadError(null);
    try {
      const payload = await getBackofficeGoogleSettings(token);
      setSettings(payload.settings);
      setEvents(payload.events || []);
      setFieldErrors({});
    } catch (error) {
      setLoadError(showApiError(error, t("seo.messages.loadFailed")));
    } finally {
      setIsLoading(false);
    }
  }, [showApiError, t, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const saveSettings = useCallback(async (payload: Partial<BackofficeGoogleSettings>) => {
    if (!token || isSaving) {
      return null;
    }
    setIsSaving(true);
    setFieldErrors({});
    try {
      const result = await updateBackofficeGoogleSettings(token, payload);
      setSettings(result.settings);
      setEvents(result.events || []);
      showSuccess(t("seo.messages.googleSettingsSaved"));
      return result.settings;
    } catch (error) {
      const nextFieldErrors: Partial<Record<"ga4_measurement_id" | "gtm_container_id", string>> = {};
      if (isApiRequestError(error) && error.payload) {
        if (Array.isArray(error.payload.ga4_measurement_id)) {
          nextFieldErrors.ga4_measurement_id = t("seo.messages.invalidGa4Id");
        }
        if (Array.isArray(error.payload.gtm_container_id)) {
          nextFieldErrors.gtm_container_id = t("seo.messages.invalidGtmId");
        }
      }
      setFieldErrors(nextFieldErrors);
      showApiError(error, t("seo.messages.actionFailed"));
      return null;
    } finally {
      setIsSaving(false);
    }
  }, [isSaving, showApiError, showSuccess, t, token]);

  const toggleEvent = useCallback(async (eventId: string, enabled: boolean) => {
    if (!token) {
      return false;
    }
    setActiveEventId(eventId);
    try {
      const result = await updateBackofficeGoogleSettings(token, {
        events: [{ id: eventId, is_enabled: enabled }],
      });
      setSettings(result.settings);
      setEvents(result.events || []);
      showSuccess(t("seo.messages.googleSettingsSaved"));
      return true;
    } catch (error) {
      showApiError(error, t("seo.messages.actionFailed"));
      return false;
    } finally {
      setActiveEventId(null);
    }
  }, [showApiError, showSuccess, t, token]);

  return {
    settings,
    events,
    isLoading,
    loadError,
    isSaving,
    activeEventId,
    fieldErrors,
    reload: load,
    saveSettings,
    toggleEvent,
  };
}
