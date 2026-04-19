"use client";

import { CarFront, Check, CircleOff } from "lucide-react";
import { useMemo } from "react";
import { useTranslations } from "next-intl";

import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import type { GarageVehicle } from "@/features/garage/types/garage";
import { formatGarageVehicleSubtitle, formatGarageVehicleTitle } from "@/features/garage/lib/vehicle-labels";

type SavedVehiclesSelectorProps = {
  vehicles: GarageVehicle[];
  isLoading: boolean;
  activeVehicleId: string | null;
  onUseVehicle: (vehicleId: string) => void;
  onClearActive: () => void;
};

export function SavedVehiclesSelector({
  vehicles,
  isLoading,
  activeVehicleId,
  onUseVehicle,
  onClearActive,
}: SavedVehiclesSelectorProps) {
  const t = useTranslations("common.header.vehicleModal");

  const safeVehicles = useMemo(() => (Array.isArray(vehicles) ? vehicles : []), [vehicles]);

  if (isLoading) {
    return (
      <p className="text-xs" style={{ color: "var(--muted)" }}>
        {t("saved.states.loading")}
      </p>
    );
  }

  if (safeVehicles.length === 0) {
    return (
      <p className="text-xs" style={{ color: "var(--muted)" }}>
        {t("saved.states.empty")}
      </p>
    );
  }

  return (
    <div>
      <div className="space-y-2">
        {safeVehicles.map((vehicle) => {
          const isActive = vehicle.id === activeVehicleId;

          return (
            <button
              key={vehicle.id}
              type="button"
              onClick={() => onUseVehicle(vehicle.id)}
              className="w-full rounded-xl border px-3 py-2 text-left transition-colors"
              style={{
                borderColor: isActive ? "var(--accent)" : "var(--border)",
                backgroundColor: isActive
                  ? "color-mix(in srgb, var(--accent) 10%, var(--surface))"
                  : "var(--surface)",
              }}
            >
              <span className="inline-flex items-center gap-2 text-sm font-medium">
                <CarFront size={14} />
                {formatGarageVehicleTitle(vehicle)}
                {isActive ? (
                  <BackofficeStatusChip tone="blue" icon={Check}>
                    {t("saved.active")}
                  </BackofficeStatusChip>
                ) : null}
              </span>
              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                {formatGarageVehicleSubtitle(vehicle) || t("saved.noDetails")}
              </p>
            </button>
          );
        })}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          className="inline-flex h-10 items-center gap-2 rounded-lg border px-3 text-sm disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          disabled={!activeVehicleId}
          onClick={onClearActive}
        >
          <CircleOff size={14} />
          {t("saved.actions.clearActive")}
        </button>
      </div>
    </div>
  );
}
