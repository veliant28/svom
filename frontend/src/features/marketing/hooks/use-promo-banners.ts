"use client";

import { useEffect, useState } from "react";

import { getPromoBanners } from "@/features/marketing/api/get-promo-banners";
import type { PromoBanner } from "@/features/marketing/types";

export function usePromoBanners(locale: string) {
  const [banners, setBanners] = useState<PromoBanner[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadBanners() {
      setIsLoading(true);
      try {
        const data = await getPromoBanners(locale);
        if (isMounted) {
          setBanners(data);
        }
      } catch {
        if (isMounted) {
          setBanners([]);
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

  return { banners, isLoading };
}
