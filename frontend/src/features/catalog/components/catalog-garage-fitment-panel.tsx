"use client";

import { CarFront, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { useCatalogFilters } from "@/features/catalog/hooks/use-catalog-filters";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { getGarageVehicles } from "@/features/garage/api/get-garage-vehicles";
import type { GarageVehicle } from "@/features/garage/types/garage";

const FITMENT_OPTION_VALUES = ["all", "only", "with_data", "unknown"] as const;

type CatalogGarageFitmentPanelProps = {
  resultCount?: number;
  isResultCountLoading?: boolean;
};

function garageVehicleLabel(vehicle: GarageVehicle): string {
  return `${vehicle.brand} ${vehicle.model}`.trim();
}

export function CatalogGarageFitmentPanel({
  resultCount,
  isResultCountLoading = false,
}: CatalogGarageFitmentPanelProps) {
  const t = useTranslations("catalog.fitment");
  const { token, isAuthenticated } = useAuth();
  const { filters, setFilters } = useCatalogFilters();
  const [garageVehicles, setGarageVehicles] = useState<GarageVehicle[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadGarageVehicles() {
      if (!token || !isAuthenticated) {
        if (isMounted) {
          setGarageVehicles([]);
          setIsLoading(false);
        }
        return;
      }

      setIsLoading(true);
      try {
        const data = await getGarageVehicles(token);
        if (isMounted) {
          setGarageVehicles(data);
        }
      } catch {
        if (isMounted) {
          setGarageVehicles([]);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadGarageVehicles();

    return () => {
      isMounted = false;
    };
  }, [token, isAuthenticated]);

  const safeGarageVehicles = Array.isArray(garageVehicles) ? garageVehicles : [];

  const selectedGarageVehicle = useMemo(
    () => safeGarageVehicles.find((vehicle) => vehicle.id === filters.garage_vehicle) ?? null,
    [safeGarageVehicles, filters.garage_vehicle],
  );

  const fitmentOptions = FITMENT_OPTION_VALUES.map((value) => ({
    value,
    label: t(`fitmentModes.${value}`),
  }));

  const hasActiveFitment = Boolean(filters.garage_vehicle || filters.fitment);
  const isControlsDisabled = isLoading;

  return (
    <section className="mx-auto max-w-6xl px-4 py-3">
      <div
        className="grid gap-3 rounded-xl border p-4 md:grid-cols-[1.3fr_1fr_auto]"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        <label className="flex flex-col gap-1 text-xs">
          <span className="inline-flex items-center gap-2">
            <CarFront size={14} />
            {t("vehicleSelectorLabel")}
          </span>
          <select
            value={filters.garage_vehicle ?? ""}
            onChange={(event) => {
              const value = event.target.value || undefined;
              setFilters({
                garage_vehicle: value,
                fitment: value ? (filters.fitment ?? "only") : undefined,
                modification: undefined,
              });
            }}
            disabled={isControlsDisabled}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">{t("vehiclePlaceholder")}</option>
            {safeGarageVehicles.map((vehicle) => (
              <option key={vehicle.id} value={vehicle.id}>
                {garageVehicleLabel(vehicle)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {t("fitmentModeLabel")}
          <select
            value={filters.fitment ?? "all"}
            onChange={(event) =>
              setFilters({
                fitment: (event.target.value || undefined) as typeof filters.fitment,
              })
            }
            disabled={isControlsDisabled}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            {fitmentOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-end justify-end">
          <button
            type="button"
            className="h-10 rounded-md border px-3 text-sm disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() =>
              setFilters({
                garage_vehicle: undefined,
                modification: undefined,
                fitment: undefined,
              })
            }
            disabled={!hasActiveFitment}
          >
            {t("clearFitment")}
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs md:col-span-2" style={{ color: "var(--muted)" }}>
          {isLoading ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 size={14} className="animate-spin" />
              {t("garageLoading")}
            </span>
          ) : selectedGarageVehicle ? (
            <BackofficeStatusChip tone="orange" icon={CarFront}>
              {garageVehicleLabel(selectedGarageVehicle)}
            </BackofficeStatusChip>
          ) : (
            <span>{t("noVehicleSelected")}</span>
          )}
        </div>

        <p className="text-xs md:col-span-1 md:text-right" style={{ color: "var(--muted)" }}>
          {isResultCountLoading
            ? t("resultCountLoading")
            : typeof resultCount === "number"
              ? t("resultCount", { count: resultCount })
              : null}
        </p>
      </div>
    </section>
  );
}
