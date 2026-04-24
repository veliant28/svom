"use client";

import { useEffect, useState } from "react";

import { getHeroSlideConfig } from "@/features/marketing/api/get-hero-slide-config";
import type { HeroSlide, HeroSlideSettings } from "@/features/marketing/types";
import {
  HERO_BLOCK_UPDATED_AT_KEY,
  HERO_BLOCK_UPDATED_EVENT,
} from "@/shared/lib/hero-block-sync";

export function useHeroSlides(locale: string) {
  const [slides, setSlides] = useState<HeroSlide[]>([]);
  const [settings, setSettings] = useState<HeroSlideSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadSlides() {
      setIsLoading(true);
      try {
        const data = await getHeroSlideConfig(locale);
        if (isMounted) {
          setSlides(data.slides || []);
          setSettings(data.settings || null);
        }
      } catch {
        if (isMounted) {
          setSlides([]);
          setSettings(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadSlides();

    return () => {
      isMounted = false;
    };
  }, [locale]);

  useEffect(() => {
    async function reloadSlides() {
      try {
        const data = await getHeroSlideConfig(locale);
        setSlides(data.slides || []);
        setSettings(data.settings || null);
      } catch {
        // keep previous state
      }
    }

    function handleStorage(event: StorageEvent) {
      if (event.key !== HERO_BLOCK_UPDATED_AT_KEY) {
        return;
      }
      void reloadSlides();
    }

    function handleUpdatedEvent() {
      void reloadSlides();
    }

    window.addEventListener("storage", handleStorage);
    window.addEventListener(HERO_BLOCK_UPDATED_EVENT, handleUpdatedEvent);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(HERO_BLOCK_UPDATED_EVENT, handleUpdatedEvent);
    };
  }, [locale]);

  return { slides, settings, isLoading };
}
