"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useLocale } from "next-intl";
import { useSearchParams } from "next/navigation";

import { getProductDetail } from "@/features/catalog/api/get-product-detail";
import { requestUtrProductEnrichment } from "@/features/catalog/api/request-utr-enrichment";
import { resolveActiveVehicleFitmentParams } from "@/features/catalog/lib/vehicle-fitment";
import type { CatalogFilters, ProductDetail } from "@/features/catalog/types";
import { useActiveVehicle } from "@/features/garage/hooks/use-active-vehicle";

export function resolveVehicleParams(params: {
  activeGarageVehicleId?: string | null;
  activeGarageVehicleCatalogSource?: "legacy" | "autodb_pro" | null;
  activeTemporaryCarModificationId?: string | number | null;
  activeVehicleSource?: "none" | "garage" | "temporary" | "temporary_autodb" | null;
  explicitParams?: Pick<CatalogFilters, "car_modification" | "garage_vehicle" | "modification">;
}): Pick<CatalogFilters, "car_modification" | "garage_vehicle" | "modification"> {
  if (params.explicitParams && Object.values(params.explicitParams).some(Boolean)) {
    return params.explicitParams;
  }
  return resolveActiveVehicleFitmentParams({
    activeVehicleSource: params.activeVehicleSource ?? "none",
    activeGarageVehicleId: params.activeGarageVehicleId ?? null,
    activeGarageVehicleCatalogSource: params.activeGarageVehicleCatalogSource ?? null,
    activeTemporaryCarModificationId:
      typeof params.activeTemporaryCarModificationId === "number"
        ? params.activeTemporaryCarModificationId
        : Number(params.activeTemporaryCarModificationId || 0) || null,
  });
}

export function useProductDetail(slug: string) {
  const locale = useLocale();
  const searchParams = useSearchParams();
  const carModificationParam = searchParams.get("car_modification") || undefined;
  const garageVehicleParam = searchParams.get("garage_vehicle") || undefined;
  const modificationParam = searchParams.get("modification") || undefined;
  const {
    activeGarageVehicleId,
    activeGarageVehicle,
    activeTemporaryCarModificationId,
    activeVehicleSource,
  } = useActiveVehicle();
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const hasResolvedInitialLoadRef = useRef(false);
  const vehicleParams = useMemo(
    () =>
      resolveVehicleParams({
        activeGarageVehicleId,
        activeGarageVehicleCatalogSource: activeGarageVehicle?.catalog_source ?? null,
        activeTemporaryCarModificationId,
        activeVehicleSource,
        explicitParams: {
          car_modification: carModificationParam,
          garage_vehicle: garageVehicleParam,
          modification: modificationParam,
        },
      }),
    [
      activeGarageVehicleId,
      activeGarageVehicle,
      activeTemporaryCarModificationId,
      activeVehicleSource,
      carModificationParam,
      garageVehicleParam,
      modificationParam,
    ],
  );

  useEffect(() => {
    let isMounted = true;

    async function load() {
      if (!hasResolvedInitialLoadRef.current) {
        setIsLoading(true);
      }
      try {
        const data = await getProductDetail(slug, locale, vehicleParams);
        if (isMounted) {
          setProduct(data);
        }
      } catch {
        if (isMounted) {
          setProduct(null);
        }
      } finally {
        if (isMounted) {
          hasResolvedInitialLoadRef.current = true;
          setIsLoading(false);
        }
      }
    }

    void load();

    return () => {
      isMounted = false;
    };
  }, [
    locale,
    slug,
    vehicleParams,
  ]);

  useEffect(() => {
    if (!product) {
      return;
    }

    let isCancelled = false;
    const currentProduct = product;

    async function warmProductDetail() {
      try {
        let statuses = await requestUtrProductEnrichment([currentProduct.id], true, "detail");
        for (let attempt = 0; attempt < 60; attempt += 1) {
          const status = statuses[0];
          const hasNewImage = Boolean(status?.primary_image) && currentProduct.images.length === 0;
          const hasNewCharacteristics = Number(status?.characteristics_count || 0) > 0 && currentProduct.attributes.length === 0;
          const hasNewFitments = Number(status?.fitments_count || 0) > 0 && currentProduct.fitments.length === 0;
          const hasProcessedUpdate = Boolean(status?.processed);
          const isStillRunning =
            Boolean(status?.needs_enrichment) || status?.status === "queued" || status?.status === "in_progress" || status?.queued;

          if (hasNewImage || hasNewCharacteristics || hasNewFitments || hasProcessedUpdate || !isStillRunning) {
            if (!isCancelled && (hasNewImage || hasNewCharacteristics || hasNewFitments || hasProcessedUpdate)) {
              const refreshed = await getProductDetail(slug, locale, vehicleParams);
              if (!isCancelled) {
                setProduct(refreshed);
              }
            }
            return;
          }

          await new Promise((resolve) => window.setTimeout(resolve, 1000));
          if (isCancelled) {
            return;
          }
          statuses = await requestUtrProductEnrichment([currentProduct.id], false, "detail");
        }
      } catch {
        // UTR enrichment is a non-blocking fallback for missing local data.
      }
    }

    void warmProductDetail();

    return () => {
      isCancelled = true;
    };
  }, [locale, product, slug, vehicleParams]);

  return { product, isLoading, vehicleParams };
}
