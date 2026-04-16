"use client";

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";

import { getProductDetail } from "@/features/catalog/api/get-product-detail";
import type { ProductDetail } from "@/features/catalog/types";

export function useProductDetail(slug: string) {
  const locale = useLocale();
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      setIsLoading(true);
      try {
        const data = await getProductDetail(slug, locale);
        if (isMounted) {
          setProduct(data);
        }
      } catch {
        if (isMounted) {
          setProduct(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void load();

    return () => {
      isMounted = false;
    };
  }, [locale, slug]);

  return { product, isLoading };
}
