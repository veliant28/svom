"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useLocale } from "next-intl";
import { useSearchParams } from "next/navigation";

import { getProductDetail } from "@/features/catalog/api/get-product-detail";
import { resolveActiveVehicleFitmentParams } from "@/features/catalog/lib/vehicle-fitment";
import type { CatalogFilters, ProductDetail } from "@/features/catalog/types";
import { useActiveVehicle } from "@/features/garage/hooks/use-active-vehicle";

export function resolveVehicleParams(params: {
  activeGarageVehicleId?: string | null;
  activeGarageVehicleCatalogSource?: "autodb_pro" | null;
  activeGarageVehicleAutoDbPassangerCarId?: number | null;
  activeTemporaryAutoDbPassangerCarId?: number | null;
  activeVehicleSource?: "none" | "garage" | "temporary_autodb" | null;
  explicitParams?: Pick<
    CatalogFilters,
    "vehicle_id" | "passanger_car_id" | "garage_vehicle" | "modification"
  >;
}): Pick<CatalogFilters, "vehicle_id" | "passanger_car_id" | "garage_vehicle" | "modification"> {
  if (params.explicitParams && Object.values(params.explicitParams).some(Boolean)) {
    return params.explicitParams;
  }
  return resolveActiveVehicleFitmentParams({
    activeVehicleSource: params.activeVehicleSource ?? "none",
    activeGarageVehicleId: params.activeGarageVehicleId ?? null,
    activeGarageVehicleCatalogSource: params.activeGarageVehicleCatalogSource ?? null,
    activeGarageVehicleAutoDbPassangerCarId: params.activeGarageVehicleAutoDbPassangerCarId ?? null,
    activeTemporaryAutoDbPassangerCarId: params.activeTemporaryAutoDbPassangerCarId ?? null,
  });
}

export function useProductDetail(slug: string) {
  const locale = useLocale();
  const searchParams = useSearchParams();
  const vehicleIdParam = searchParams?.get("vehicle_id") || undefined;
  const passangerCarIdParam = searchParams?.get("passanger_car_id") || undefined;
  const garageVehicleParam = searchParams?.get("garage_vehicle") || undefined;
  const modificationParam = searchParams?.get("modification") || undefined;
  const {
    activeGarageVehicleId,
    activeGarageVehicle,
    activeTemporaryAutoDbPassangerCarId,
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
        activeGarageVehicleAutoDbPassangerCarId: activeGarageVehicle?.autodb_passanger_car_id ?? null,
        activeTemporaryAutoDbPassangerCarId,
        activeVehicleSource,
        explicitParams: {
          vehicle_id: vehicleIdParam,
          passanger_car_id: passangerCarIdParam,
          garage_vehicle: garageVehicleParam,
          modification: modificationParam,
        },
      }),
    [
      activeGarageVehicleId,
      activeGarageVehicle,
      activeTemporaryAutoDbPassangerCarId,
      activeVehicleSource,
      vehicleIdParam,
      passangerCarIdParam,
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

  return { product, isLoading, vehicleParams };
}
