"use client";

import { CarFront } from "lucide-react";
import { useTranslations } from "next-intl";

import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import type { GarageVehicle } from "@/features/garage/types/garage";

function formatPower(vehicle: GarageVehicle, fallbackLabel: string): string {
  const hp = vehicle.power_hp ? `${vehicle.power_hp} л.с.` : "";
  const kw = vehicle.power_kw ? `${vehicle.power_kw} кВт` : "";

  if (hp && kw) {
    return `${hp} / ${kw}`;
  }
  if (hp) {
    return hp;
  }
  if (kw) {
    return kw;
  }
  return fallbackLabel;
}

export function GarageVehicleCard({
  vehicle,
  isActionLoading,
  onSetPrimary,
  onDelete,
}: {
  vehicle: GarageVehicle;
  isActionLoading: boolean;
  onSetPrimary: (vehicleId: string) => Promise<void>;
  onDelete: (vehicleId: string) => Promise<void>;
}) {
  const t = useTranslations("garage.card");

  return (
    <article
      className="rounded-xl border p-4"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold">
          {vehicle.brand} {vehicle.model}
        </p>
        {vehicle.is_primary ? (
          <BackofficeStatusChip tone="success" icon={CarFront}>
            {t("primary")}
          </BackofficeStatusChip>
        ) : null}
      </div>

      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {t("labels.year")}: {vehicle.year ?? t("fallback.year")}
      </p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {t("labels.modification")}: {vehicle.modification || t("fallback.modification")}
      </p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {t("labels.engine")}: {vehicle.engine || t("fallback.engine")}
      </p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {t("labels.power")}: {formatPower(vehicle, t("fallback.power"))}
      </p>

      <div className="mt-3 flex items-center gap-2">
        {!vehicle.is_primary ? (
          <button
            type="button"
            onClick={() => void onSetPrimary(vehicle.id)}
            disabled={isActionLoading}
            className="h-8 rounded-md border px-2 text-xs disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            {t("actions.makePrimary")}
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => void onDelete(vehicle.id)}
          disabled={isActionLoading}
          className="h-8 rounded-md border px-2 text-xs disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          {t("actions.delete")}
        </button>
      </div>
      {isActionLoading ? (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          {t("actions.pending")}
        </p>
      ) : null}
    </article>
  );
}
