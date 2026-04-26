"use client";

import { Filter, Loader2, Save, Star } from "lucide-react";
import { useState } from "react";
import { useTranslations } from "next-intl";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { useVehicleCascade } from "@/features/garage/hooks/use-vehicle-cascade";
import { formatEngineLabel } from "@/features/garage/lib/vehicle-labels";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

type SaveMode = "save" | null;

type NewVehicleSelectionFormProps = {
  isAuthenticated: boolean;
  onUseTemporary: (carModificationId: number) => void;
  onSaveVehicle: (payload: { car_modification: number; is_primary?: boolean }) => Promise<void>;
};

export function NewVehicleSelectionForm({
  isAuthenticated,
  onUseTemporary,
  onSaveVehicle,
}: NewVehicleSelectionFormProps) {
  const tGarage = useTranslations("garage.form");
  const t = useTranslations("common.header.vehicleModal");
  const cascade = useVehicleCascade();
  const { showApiError, showSuccess } = useStorefrontFeedback();

  const [isPrimary, setIsPrimary] = useState(false);
  const [activeSaveMode, setActiveSaveMode] = useState<SaveMode>(null);

  const hasSelectedEngine = Boolean(cascade.selectedEngine);
  const canUseForFiltering = hasSelectedEngine;
  const canSave = isAuthenticated && hasSelectedEngine;
  const canTogglePrimary = isAuthenticated && hasSelectedEngine;
  const isSubmitting = activeSaveMode !== null;

  return (
    <div>
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs">
          {tGarage("fields.year.label")}
          <select
            value={cascade.selectedYear}
            onChange={(event) => cascade.setSelectedYear(event.target.value)}
            disabled={cascade.isLoadingYears || isSubmitting}
            className="h-10 rounded-lg border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {cascade.isLoadingYears ? tGarage("fields.year.loadingPlaceholder") : tGarage("fields.year.anyOption")}
            </option>
            {cascade.years.map((year) => (
              <option key={year.year} value={year.year}>
                {year.year}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {tGarage("fields.make.label")}
          <select
            value={cascade.selectedMake}
            onChange={(event) => cascade.setSelectedMake(event.target.value)}
            disabled={!cascade.selectedYear || cascade.isLoadingMakes || isSubmitting}
            className="h-10 rounded-lg border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {cascade.isLoadingMakes ? tGarage("fields.make.loadingPlaceholder") : tGarage("fields.make.placeholder")}
            </option>
            {cascade.makes.map((make) => (
              <option key={make.id} value={make.id}>
                {make.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {tGarage("fields.model.label")}
          <select
            value={cascade.selectedModel}
            onChange={(event) => cascade.setSelectedModel(event.target.value)}
            disabled={!cascade.selectedMake || cascade.isLoadingModels || isSubmitting}
            className="h-10 rounded-lg border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {cascade.isLoadingModels ? tGarage("fields.model.loadingPlaceholder") : tGarage("fields.model.placeholder")}
            </option>
            {cascade.models.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {tGarage("fields.modification.label")}
          <select
            value={cascade.selectedModification}
            onChange={(event) => cascade.setSelectedModification(event.target.value)}
            disabled={!cascade.selectedModel || cascade.isLoadingModifications || isSubmitting}
            className="h-10 rounded-lg border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {cascade.isLoadingModifications ? tGarage("fields.modification.loadingPlaceholder") : tGarage("fields.modification.placeholder")}
            </option>
            {cascade.modifications.map((modification) => (
              <option key={modification.modification} value={modification.modification}>
                {modification.modification}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {tGarage("fields.capacity.label")}
          <select
            value={cascade.selectedCapacity}
            onChange={(event) => cascade.setSelectedCapacity(event.target.value)}
            disabled={!cascade.selectedModification || cascade.isLoadingCapacities || isSubmitting}
            className="h-10 rounded-lg border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {cascade.isLoadingCapacities ? tGarage("fields.capacity.loadingPlaceholder") : tGarage("fields.capacity.placeholder")}
            </option>
            {cascade.capacities.map((capacity) => (
              <option key={capacity.capacity} value={capacity.capacity}>
                {capacity.capacity}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {tGarage("fields.engine.label")}
          <select
            value={cascade.selectedEngine}
            onChange={(event) => cascade.setSelectedEngine(event.target.value)}
            disabled={!cascade.selectedCapacity || cascade.isLoadingEngines || isSubmitting}
            className="h-10 rounded-lg border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {cascade.isLoadingEngines ? tGarage("fields.engine.loadingPlaceholder") : tGarage("fields.engine.placeholder")}
            </option>
            {cascade.engines.map((engine) => (
              <option key={engine.id} value={engine.id}>
                {formatEngineLabel(engine)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <BackofficeTooltip
          content={tGarage("fields.isPrimary")}
          placement="top"
          align="center"
          wrapperClassName="inline-flex"
          tooltipClassName="whitespace-nowrap"
        >
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border disabled:opacity-60"
            style={{
              borderColor: isPrimary ? "var(--accent)" : "var(--border)",
              backgroundColor: isPrimary
                ? "color-mix(in srgb, var(--accent) 12%, var(--surface))"
                : "var(--surface)",
            }}
            disabled={!canTogglePrimary || isSubmitting}
            onClick={() => setIsPrimary((prev) => !prev)}
            aria-label={tGarage("fields.isPrimary")}
          >
            <Star size={15} />
          </button>
        </BackofficeTooltip>

        <BackofficeTooltip
          content={t("new.actions.useForFiltering")}
          placement="top"
          align="center"
          wrapperClassName="inline-flex"
          tooltipClassName="whitespace-nowrap"
        >
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={!canUseForFiltering || isSubmitting}
            onClick={() => {
              const carModificationId = Number(cascade.selectedEngine);
              if (!Number.isInteger(carModificationId) || carModificationId <= 0) {
                return;
              }
              onUseTemporary(carModificationId);
              showSuccess(t("new.messages.usedForFiltering"));
            }}
            aria-label={t("new.actions.useForFiltering")}
          >
            <Filter size={15} />
          </button>
        </BackofficeTooltip>

        <BackofficeTooltip
          content={activeSaveMode === "save" ? t("new.actions.saving") : t("new.actions.saveToGarage")}
          placement="top"
          align="center"
          wrapperClassName="inline-flex"
          tooltipClassName="whitespace-nowrap"
        >
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={!canSave || isSubmitting}
            onClick={async () => {
              const carModificationId = Number(cascade.selectedEngine);
              if (!Number.isInteger(carModificationId) || carModificationId <= 0) {
                return;
              }
              setActiveSaveMode("save");
              try {
                await onSaveVehicle({ car_modification: carModificationId, is_primary: isPrimary });
                showSuccess(t("new.messages.savedToGarage"));
              } catch (error) {
                showApiError(error, t("new.messages.saveFailed"));
              } finally {
                setActiveSaveMode(null);
              }
            }}
            aria-label={activeSaveMode === "save" ? t("new.actions.saving") : t("new.actions.saveToGarage")}
          >
            {activeSaveMode === "save" ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
          </button>
        </BackofficeTooltip>
      </div>

      {!isAuthenticated ? (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          {t("new.messages.authRequiredForSave")}
        </p>
      ) : null}
    </div>
  );
}
