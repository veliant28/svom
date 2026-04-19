"use client";

import { useTranslations } from "next-intl";

import { GarageEmptyState } from "@/features/garage/components/garage-empty-state";
import { GarageVehicleCard } from "@/features/garage/components/garage-vehicle-card";
import { useGarageVehicles } from "@/features/garage/hooks/use-garage-vehicles";

export function GaragePage() {
  const t = useTranslations("garage.page");
  const {
    garageVehicles,
    isLoading,
    isActionLoading,
    setPrimaryGarageVehicle,
    removeGarageVehicle,
  } = useGarageVehicles();

  // Final UI guard: even if API shape changes again, the page keeps rendering safely.
  const safeGarageVehicles = Array.isArray(garageVehicles) ? garageVehicles : [];

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        {t("subtitle")}
      </p>

      <div className="mt-4 rounded-xl border px-3 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        {t("addFromHeaderHint")}
      </div>

      <div className="mt-5">
        {isLoading ? (
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            {t("states.loading")}
          </p>
        ) : safeGarageVehicles.length === 0 ? (
          <GarageEmptyState />
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {safeGarageVehicles.map((vehicle) => (
              <GarageVehicleCard
                key={vehicle.id}
                vehicle={vehicle}
                isActionLoading={isActionLoading}
                onSetPrimary={setPrimaryGarageVehicle}
                onDelete={removeGarageVehicle}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
