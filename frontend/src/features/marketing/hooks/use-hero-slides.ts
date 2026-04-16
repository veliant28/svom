"use client";

import { useEffect, useState } from "react";

import { getHeroSlides } from "@/features/marketing/api/get-hero-slides";
import type { HeroSlide } from "@/features/marketing/types";

export function useHeroSlides(locale: string) {
  const [slides, setSlides] = useState<HeroSlide[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadSlides() {
      setIsLoading(true);
      try {
        const data = await getHeroSlides(locale);
        if (isMounted) {
          setSlides(data);
        }
      } catch {
        if (isMounted) {
          setSlides([]);
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

  return { slides, isLoading };
}
