"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale } from "next-intl";

import { getProducts } from "@/features/catalog/api/get-products";
import {
  buildCatalogCacheKey,
  CATALOG_CACHE_UPDATED_EVENT,
  type CachedCatalogPayload,
  readCachedCatalogPayload,
  writeCachedCatalogPayload,
} from "@/features/catalog/lib/catalog-page-cache";
import { resolveActiveVehicleFitmentParams } from "@/features/catalog/lib/vehicle-fitment";
import { useActiveVehicle } from "@/features/garage/hooks/use-active-vehicle";
import type { CatalogFilters, CatalogProduct } from "@/features/catalog/types";

type UseCatalogProductsParams = CatalogFilters & { page?: number; pageSize?: number };

type UseCatalogProductsOptions = {
  enabled?: boolean;
  useActiveVehicle?: boolean;
  deferCachedRevalidation?: boolean;
};

export function useCatalogProducts(params: UseCatalogProductsParams = {}, options: UseCatalogProductsOptions = {}) {
  const locale = useLocale();
  const {
    activeGarageVehicleId,
    activeGarageVehicle,
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
        Object.assign(
          result,
          resolveActiveVehicleFitmentParams({
            activeVehicleSource,
            activeGarageVehicleId,
            activeGarageVehicleCatalogSource: activeGarageVehicle?.catalog_source ?? null,
            activeTemporaryCarModificationId,
          }),
        );
      }

      const hasActiveVehicle = Boolean(result.garage_vehicle || result.car_modification);
      if (hasActiveVehicle && !result.fitment) {
        result.fitment = "only";
      }
    }

    return result;
  }, [
    activeGarageVehicleId,
    activeGarageVehicle,
    activeTemporaryCarModificationId,
    activeVehicleSource,
    options.useActiveVehicle,
    baseParams,
  ]);
  const paramsKey = JSON.stringify({ ...effectiveParams, locale });
  const cacheKey = useMemo(() => buildCatalogCacheKey(paramsKey), [paramsKey]);
  const isEnabled = options.enabled ?? true;
  const deferCachedRevalidation = options.deferCachedRevalidation ?? false;

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
        if (deferCachedRevalidation) {
          return;
        }
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
  }, [cacheKey, deferCachedRevalidation, effectiveParams, isEnabled, locale, paramsKey]);

  useEffect(() => {
    if (!isEnabled || typeof window === "undefined") {
      return;
    }

    const handleCacheUpdated = (event: Event) => {
      const customEvent = event as CustomEvent<{
        cacheKey?: string;
        payload?: CachedCatalogPayload;
      }>;
      const updatedKey = customEvent.detail?.cacheKey;
      const payload = customEvent.detail?.payload;
      if (updatedKey !== cacheKey || !payload) {
        return;
      }
      setProducts(payload.products);
      setTotalCount(payload.totalCount);
      setIsLoading(false);
    };

    window.addEventListener(CATALOG_CACHE_UPDATED_EVENT, handleCacheUpdated);
    return () => {
      window.removeEventListener(CATALOG_CACHE_UPDATED_EVENT, handleCacheUpdated);
    };
  }, [cacheKey, isEnabled]);

  return { products, totalCount, isLoading, cacheKey };
}
