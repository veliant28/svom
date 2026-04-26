"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale } from "next-intl";

import { getProducts } from "@/features/catalog/api/get-products";
import { requestUtrProductEnrichment, type UtrEnrichmentStatus } from "@/features/catalog/api/request-utr-enrichment";
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
  const isEnabled = options.enabled ?? true;
  const productIdsKey = useMemo(() => products.map((product) => product.id).join("|"), [products]);

  useEffect(() => {
    if (!isEnabled) {
      setProducts((previous) => (previous.length > 0 ? [] : previous));
      setTotalCount((previous) => (previous === 0 ? previous : 0));
      setIsLoading((previous) => (previous ? false : previous));
      return;
    }

    let isMounted = true;

    async function loadProducts() {
      setIsLoading(true);
      try {
        const response = await getProducts({ ...effectiveParams, pageSize: effectiveParams.pageSize, locale });
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
  }, [effectiveParams, isEnabled, locale, paramsKey]);

  useEffect(() => {
    if (!isEnabled || isLoading || !productIdsKey) {
      return;
    }

    let isCancelled = false;
    const productIds = productIdsKey.split("|").filter(Boolean);

    const applyStatuses = (statuses: UtrEnrichmentStatus[]) => {
      const statusByProductId = new Map(statuses.map((item) => [item.product_id, item]));
      setProducts((current) =>
        current.map((product) => {
          const status = statusByProductId.get(product.id);
          if (!status?.primary_image || status.primary_image === product.primary_image) {
            return product;
          }
          return { ...product, primary_image: status.primary_image };
        }),
      );
    };

    const shouldPoll = (statuses: UtrEnrichmentStatus[]) =>
      statuses.some((item) => item.status === "queued" || item.status === "in_progress" || item.queued);

    async function warmVisibleProducts() {
      try {
        let statuses = await requestUtrProductEnrichment(productIds, true);
        if (isCancelled) {
          return;
        }
        applyStatuses(statuses);

        for (let attempt = 0; attempt < 8 && shouldPoll(statuses); attempt += 1) {
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
          if (isCancelled) {
            return;
          }
          statuses = await requestUtrProductEnrichment(productIds, false);
          if (isCancelled) {
            return;
          }
          applyStatuses(statuses);
        }
      } catch {
        // Enrichment is opportunistic; catalog rendering must not depend on UTR.
      }
    }

    void warmVisibleProducts();

    return () => {
      isCancelled = true;
    };
  }, [isEnabled, isLoading, productIdsKey]);

  return { products, totalCount, isLoading };
}
