"use client";

import { CarFront, Star, Trash2 } from "lucide-react";
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
      className="flex h-full flex-col rounded-xl border p-3"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-semibold">
          {vehicle.brand} {vehicle.model}
        </p>
        {vehicle.is_primary ? (
          <BackofficeStatusChip tone="success" icon={CarFront}>
            {t("primary")}
          </BackofficeStatusChip>
        ) : (
          <span className="group relative inline-flex">
            <button
              type="button"
              onClick={() => void onSetPrimary(vehicle.id)}
              disabled={isActionLoading}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border disabled:opacity-60"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              aria-label={t("actions.makePrimary")}
            >
              <Star size={14} />
            </button>
            <span
              role="tooltip"
              className="pointer-events-none absolute left-1/2 top-full z-20 mt-1 hidden -translate-x-1/2 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[10px] group-hover:block"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
            >
              {t("actions.makePrimary")}
            </span>
          </span>
        )}
      </div>

      <p className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
        {t("labels.year")}: {vehicle.year ?? t("fallback.year")}
      </p>
      <p className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
        {t("labels.modification")}: {vehicle.modification || t("fallback.modification")}
      </p>
      <p className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
        {t("labels.engine")}: {vehicle.engine || t("fallback.engine")}
      </p>
      <p className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
        {t("labels.power")}: {formatPower(vehicle, t("fallback.power"))}
      </p>

      <div className="mt-auto flex justify-end pt-2">
        <span className="group relative inline-flex">
          <button
            type="button"
            onClick={() => void onDelete(vehicle.id)}
            disabled={isActionLoading}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
            style={{
              borderColor: "#ef4444",
              backgroundColor: "var(--surface)",
              color: "#dc2626",
            }}
            aria-label={t("actions.delete")}
          >
            <Trash2 size={14} />
          </button>
          <span
            role="tooltip"
            className="pointer-events-none absolute left-1/2 top-full z-20 mt-1 hidden -translate-x-1/2 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[10px] group-hover:block"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
          >
            {t("actions.delete")}
          </span>
        </span>
      </div>
      {isActionLoading ? (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          {t("actions.pending")}
        </p>
      ) : null}
    </article>
  );
}
