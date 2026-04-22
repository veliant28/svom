"use client";

import { useCallback, useEffect, useState } from "react";

import { getFooterSettings } from "@/features/marketing/api/get-footer-settings";
import type { MarketingFooterSettings } from "@/features/marketing/types";
import {
  FOOTER_SETTINGS_UPDATED_AT_KEY,
  FOOTER_SETTINGS_UPDATED_EVENT,
} from "@/shared/lib/footer-settings-sync";

export function useFooterSettings() {
  const [settings, setSettings] = useState<MarketingFooterSettings | null>(null);

  const load = useCallback(async () => {
    try {
      const payload = await getFooterSettings();
      setSettings(payload);
    } catch {
      // Keep fallback values from i18n when API is unavailable.
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    function handleStorage(event: StorageEvent) {
      if (event.key === FOOTER_SETTINGS_UPDATED_AT_KEY) {
        void load();
      }
    }
    function handleUpdatedEvent() {
      void load();
    }

    window.addEventListener("storage", handleStorage);
    window.addEventListener(FOOTER_SETTINGS_UPDATED_EVENT, handleUpdatedEvent);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(FOOTER_SETTINGS_UPDATED_EVENT, handleUpdatedEvent);
    };
  }, [load]);

  return { settings, reload: load };
}
