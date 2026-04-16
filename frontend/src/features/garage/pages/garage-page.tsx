"use client";

import { useTranslations } from "next-intl";

import { GarageAddVehicleForm } from "@/features/garage/components/garage-add-vehicle-form";
import { GarageEmptyState } from "@/features/garage/components/garage-empty-state";
import { GarageVehicleCard } from "@/features/garage/components/garage-vehicle-card";
import { useGarageVehicles } from "@/features/garage/hooks/use-garage-vehicles";

export function GaragePage() {
  const t = useTranslations("garage.page");
  const {
    garageVehicles,
    isLoading,
    isActionLoading,
    error,
    refreshGarageVehicles,
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

      <div className="mt-5 grid gap-4 lg:grid-cols-[360px_1fr]">
        <GarageAddVehicleForm onCreated={refreshGarageVehicles} />

        <div>
          {isLoading ? (
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {t("states.loading")}
            </p>
          ) : error ? (
            <p className="text-sm" style={{ color: "var(--danger, #b42318)" }}>
              {t("states.error")}
            </p>
          ) : safeGarageVehicles.length === 0 ? (
            <GarageEmptyState />
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
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
      </div>
    </section>
  );
}
