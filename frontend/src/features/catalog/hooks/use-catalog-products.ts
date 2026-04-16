"use client";

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";

import { getProducts } from "@/features/catalog/api/get-products";
import type { CatalogFilters, CatalogProduct } from "@/features/catalog/types";

type UseCatalogProductsParams = CatalogFilters & { pageSize?: number };

export function useCatalogProducts(params: UseCatalogProductsParams = {}, options: { enabled?: boolean } = {}) {
  const locale = useLocale();
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const paramsKey = JSON.stringify({ ...params, locale });
  const isEnabled = options.enabled ?? true;

  useEffect(() => {
    if (!isEnabled) {
      setProducts([]);
      setTotalCount(0);
      setIsLoading(false);
      return;
    }

    let isMounted = true;

    async function loadProducts() {
      setIsLoading(true);
      try {
        const response = await getProducts({ ...params, pageSize: params.pageSize, locale });
        if (isMounted) {
          setProducts(response.results);
          setTotalCount(response.count);
        }
      } catch {
        if (isMounted) {
          setProducts([]);
          setTotalCount(0);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadProducts();

    return () => {
      isMounted = false;
    };
  }, [isEnabled, locale, paramsKey]);

  return { products, totalCount, isLoading };
}
