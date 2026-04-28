"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale } from "next-intl";

import { getProducts } from "@/features/catalog/api/get-products";
import { buildCatalogCacheKey, readCachedCatalogPayload, writeCachedCatalogPayload } from "@/features/catalog/lib/catalog-page-cache";
import { useActiveVehicle } from "@/features/garage/hooks/use-active-vehicle";
import type { CatalogFilters, CatalogProduct } from "@/features/catalog/types";

type UseCatalogProductsParams = CatalogFilters & { page?: number; pageSize?: number };

type UseCatalogProductsOptions = {
  enabled?: boolean;
  useActiveVehicle?: boolean;
};

export function useCatalogProducts(params: UseCatalogProductsParams = {}, options: UseCatalogProductsOptions = {}) {
  const locale = useLocale();
  const {
    activeGarageVehicleId,
    activeTemporaryCarModificationId,
    activeVehicleSource,
  } = useActiveVehicle();
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const baseParamsKey = useMemo(() => {
    try {
      return JSON.stringify(params ?? {});
    } catch {
      return "{}";
    }
  }, [params]);
  const baseParams = useMemo<UseCatalogProductsParams>(() => {
    try {
      return JSON.parse(baseParamsKey) as UseCatalogProductsParams;
    } catch {
      return {};
    }
  }, [baseParamsKey]);
  const effectiveParams = useMemo(() => {
    const result: UseCatalogProductsParams = { ...baseParams };

    if (options.useActiveVehicle) {
      const hasExplicitVehicle = Boolean(result.garage_vehicle || result.car_modification);
      if (!hasExplicitVehicle) {
        if (activeVehicleSource === "garage" && activeGarageVehicleId) {
          result.garage_vehicle = activeGarageVehicleId;
        } else if (activeVehicleSource === "temporary" && activeTemporaryCarModificationId) {
          result.car_modification = String(activeTemporaryCarModificationId);
        }
      }

      const hasActiveVehicle = Boolean(result.garage_vehicle || result.car_modification);
      if (hasActiveVehicle && !result.fitment) {
        result.fitment = "only";
      }
    }

    return result;
  }, [
    activeGarageVehicleId,
    activeTemporaryCarModificationId,
    activeVehicleSource,
    options.useActiveVehicle,
    baseParams,
  ]);
  const paramsKey = JSON.stringify({ ...effectiveParams, locale });
  const cacheKey = useMemo(() => buildCatalogCacheKey(paramsKey), [paramsKey]);
  const isEnabled = options.enabled ?? true;

  useEffect(() => {
    if (!isEnabled) {
      setProducts((previous) => (previous.length > 0 ? [] : previous));
      setTotalCount((previous) => (previous === 0 ? previous : 0));
      setIsLoading((previous) => (previous ? false : previous));
      return;
    }

    let isMounted = true;

    async function loadProducts() {
      const cached = readCachedCatalogPayload(cacheKey);
      if (cached) {
        setProducts(cached.products);
        setTotalCount(cached.totalCount);
        setIsLoading(false);
      } else {
        setIsLoading(true);
        setProducts([]);
      }
      try {
        const response = await getProducts({ ...effectiveParams, pageSize: effectiveParams.pageSize, locale });
        if (isMounted) {
          setProducts(response.results);
          setTotalCount(response.count);
          setIsLoading(false);
          writeCachedCatalogPayload(cacheKey, {
            products: response.results,
            totalCount: response.count,
          });
        }
      } catch {
        if (isMounted && !cached) {
          setProducts([]);
          setTotalCount(0);
          setIsLoading(false);
        }
      }
    }

    void loadProducts();

    return () => {
      isMounted = false;
    };
  }, [cacheKey, effectiveParams, isEnabled, locale, paramsKey]);

  return { products, totalCount, isLoading, cacheKey };
}
