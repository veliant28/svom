"use client";

import { useEffect, useState } from "react";

import { getPromoBannerConfig } from "@/features/marketing/api/get-promo-banner-config";
import type { PromoBanner, PromoBannerSettings } from "@/features/marketing/types";
import {
  PROMO_BANNERS_UPDATED_AT_KEY,
  PROMO_BANNERS_UPDATED_EVENT,
} from "@/shared/lib/promo-banners-sync";

export function usePromoBanners(locale: string) {
  const [banners, setBanners] = useState<PromoBanner[]>([]);
  const [settings, setSettings] = useState<PromoBannerSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadBanners() {
      setIsLoading(true);
      try {
        const data = await getPromoBannerConfig(locale);
        if (isMounted) {
          setBanners(data.banners || []);
          setSettings(data.settings || null);
        }
      } catch {
        if (isMounted) {
          setBanners([]);
          setSettings(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadBanners();

    return () => {
      isMounted = false;
    };
  }, [locale]);

  useEffect(() => {
    function handleStorage(event: StorageEvent) {
      if (event.key !== PROMO_BANNERS_UPDATED_AT_KEY) {
        return;
      }
      void (async () => {
        try {
          const data = await getPromoBannerConfig(locale);
          setBanners(data.banners || []);
          setSettings(data.settings || null);
        } catch {
          // keep previous state
        }
      })();
    }

    function handleUpdatedEvent() {
      void (async () => {
        try {
          const data = await getPromoBannerConfig(locale);
          setBanners(data.banners || []);
          setSettings(data.settings || null);
        } catch {
          // keep previous state
        }
      })();
    }

    window.addEventListener("storage", handleStorage);
    window.addEventListener(PROMO_BANNERS_UPDATED_EVENT, handleUpdatedEvent);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(PROMO_BANNERS_UPDATED_EVENT, handleUpdatedEvent);
    };
  }, [locale]);

  return { banners, settings, isLoading };
}
