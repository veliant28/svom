"use client";

import { Filter, Loader2, Save, Star } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getAutoDbVehicleCatalog,
  getAutoDbVehicleFilterOptions,
} from "@/features/garage/api/autodb-vehicles";
import { normalizeDisplayText } from "@/features/garage/lib/clean-text";
import type { GarageVehicleCreatePayload } from "@/features/garage/types/garage";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

type SaveMode = "save" | null;

function parsePowerValue(raw: string): number | null {
  const text = String(raw || "").trim();
  if (!text) {
    return null;
  }
  const match = text.match(/\d+/);
  if (!match) {
    return null;
  }
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

type NewVehicleSelectionFormProps = {
  isAuthenticated: boolean;
  onUseTemporaryAutoDb: (payload: { manufacturerId: number; modelId: number; passangerCarId: number }) => void;
  onSaveVehicle: (payload: GarageVehicleCreatePayload) => Promise<void>;
};

function AutoDbSelectionForm({
  isAuthenticated,
  onUseTemporaryAutoDb,
  onSaveVehicle,
}: {
  isAuthenticated: boolean;
  onUseTemporaryAutoDb: (payload: { manufacturerId: number; modelId: number; passangerCarId: number }) => void;
  onSaveVehicle: (payload: GarageVehicleCreatePayload) => Promise<void>;
}) {
  const tGarage = useTranslations("garage.form");
  const t = useTranslations("common.header.vehicleModal");
  const { showApiError, showError, showSuccess } = useStorefrontFeedback();

  const [selectedYear, setSelectedYear] = useState<string>("");
  const [selectedManufacturerId, setSelectedManufacturerId] = useState<string>("");
  const [selectedModelId, setSelectedModelId] = useState<string>("");
  const [selectedModification, setSelectedModification] = useState<string>("");
  const [selectedCapacity, setSelectedCapacity] = useState<string>("");
  const [selectedEngine, setSelectedEngine] = useState<string>("");

  const [years, setYears] = useState<number[]>([]);
  const [manufacturers, setManufacturers] = useState<Array<{ id: number; name: string }>>([]);
  const [models, setModels] = useState<Array<{ id: number; name: string }>>([]);
  const [modifications, setModifications] = useState<string[]>([]);
  const [capacities, setCapacities] = useState<string[]>([]);
  const [engines, setEngines] = useState<string[]>([]);
  const [matchingRows, setMatchingRows] = useState<
    Array<{
      passanger_car_id: number;
      manufacturer_id: number | null;
      model_id: number | null;
      make: string;
      model: string;
      modification: string;
      period: string;
      volume: string;
      engine: string;
      hp: string;
      kw: string;
    }>
  >([]);

  const [isLoadingOptions, setIsLoadingOptions] = useState(false);
  const [isLoadingRows, setIsLoadingRows] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [isPrimary, setIsPrimary] = useState(false);
  const [activeSaveMode, setActiveSaveMode] = useState<SaveMode>(null);

  useEffect(() => {
    if (!loadError) {
      return;
    }
    showError(t("new.messages.saveFailed"));
  }, [loadError, showError, t]);

  useEffect(() => {
    let isMounted = true;
    async function loadYears() {
      setIsLoadingOptions(true);
      setLoadError(null);
      try {
        const payload = await getAutoDbVehicleFilterOptions({ years_only: true });
        if (isMounted) {
          setYears(payload.years);
        }
      } catch {
        if (isMounted) {
          setYears([]);
          setLoadError("catalog_unavailable");
        }
      } finally {
        if (isMounted) {
          setIsLoadingOptions(false);
        }
      }
    }
    void loadYears();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedYear) {
      setManufacturers([]);
      setModels([]);
      setModifications([]);
      setCapacities([]);
      setEngines([]);
      return;
    }

    let isMounted = true;
    async function loadOptions() {
      setIsLoadingOptions(true);
      setLoadError(null);
      try {
        const payload = await getAutoDbVehicleFilterOptions({
          year: Number(selectedYear),
          manufacturer_id: selectedManufacturerId ? Number(selectedManufacturerId) : undefined,
          model_id: selectedModelId ? Number(selectedModelId) : undefined,
          modification: selectedModification || undefined,
          volume: selectedCapacity || undefined,
        });
        if (isMounted) {
          setManufacturers(payload.manufacturers);
          setModels(payload.models);
          setModifications(payload.modifications);
          setCapacities(payload.volumes);
          setEngines(payload.engines);

          if (selectedManufacturerId && !payload.manufacturers.some((row) => String(row.id) === selectedManufacturerId)) {
            setSelectedManufacturerId("");
          }
          if (selectedModelId && !payload.models.some((row) => String(row.id) === selectedModelId)) {
            setSelectedModelId("");
          }
          if (selectedModification && !payload.modifications.includes(selectedModification)) {
            setSelectedModification("");
          }
          if (selectedCapacity && !payload.volumes.includes(selectedCapacity)) {
            setSelectedCapacity("");
          }
          if (selectedEngine && !payload.engines.includes(selectedEngine)) {
            setSelectedEngine("");
          }
        }
      } catch {
        if (isMounted) {
          setManufacturers([]);
          setModels([]);
          setModifications([]);
          setCapacities([]);
          setEngines([]);
          setLoadError("catalog_unavailable");
        }
      } finally {
        if (isMounted) {
          setIsLoadingOptions(false);
        }
      }
    }
    void loadOptions();
    return () => {
      isMounted = false;
    };
  }, [selectedYear, selectedManufacturerId, selectedModelId, selectedModification, selectedCapacity, selectedEngine]);

  useEffect(() => {
    if (!selectedManufacturerId || !selectedModelId || !selectedModification || !selectedCapacity) {
      setMatchingRows([]);
      return;
    }

    let isMounted = true;
    async function loadRows() {
      setIsLoadingRows(true);
      setLoadError(null);
      try {
        const payload = await getAutoDbVehicleCatalog({
          year: selectedYear ? Number(selectedYear) : undefined,
          manufacturer_id: Number(selectedManufacturerId),
          model_id: Number(selectedModelId),
          modification: selectedModification,
          volume: selectedCapacity,
          page: 1,
          page_size: 500,
        });
        if (isMounted) {
          setMatchingRows(payload.results);
          if (selectedEngine && !payload.results.some((row) => row.engine === selectedEngine)) {
            setSelectedEngine("");
          }
        }
      } catch {
        if (isMounted) {
          setMatchingRows([]);
          setLoadError("catalog_unavailable");
        }
      } finally {
        if (isMounted) {
          setIsLoadingRows(false);
        }
      }
    }
    void loadRows();

    return () => {
      isMounted = false;
    };
  }, [selectedYear, selectedManufacturerId, selectedModelId, selectedModification, selectedCapacity, selectedEngine]);

  const selectedRow = useMemo(
    () => matchingRows.find((row) => row.engine === selectedEngine) ?? null,
    [matchingRows, selectedEngine],
  );

  const composedLabel = useMemo(() => {
    if (!selectedRow) {
      return "";
    }
    return normalizeDisplayText(
      [selectedRow.make, selectedRow.model, selectedRow.modification, selectedRow.engine, selectedRow.period]
        .filter(Boolean)
        .join(", "),
    );
  }, [selectedRow]);

  const hasSelectedPassangerCar = Boolean(selectedRow?.passanger_car_id);
  const canTogglePrimary = isAuthenticated && hasSelectedPassangerCar;
  const canUseForFiltering = hasSelectedPassangerCar;
  const canSave = isAuthenticated && hasSelectedPassangerCar;
  const isSubmitting = activeSaveMode !== null;

  return (
    <div>
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs">
          {tGarage("fields.year.label")}
          <select
            value={selectedYear}
            onChange={(event) => {
              setSelectedYear(event.target.value);
              setSelectedManufacturerId("");
              setSelectedModelId("");
              setSelectedModification("");
              setSelectedCapacity("");
              setSelectedEngine("");
            }}
            disabled={isLoadingOptions || isSubmitting}
            className="h-10 rounded-lg border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">{isLoadingOptions ? tGarage("fields.year.loadingPlaceholder") : tGarage("fields.year.anyOption")}</option>
            {years.map((year) => (
              <option key={year} value={String(year)}>
                {year}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {tGarage("fields.make.label")}
          <select
            value={selectedManufacturerId}
            onChange={(event) => {
              setSelectedManufacturerId(event.target.value);
              setSelectedModelId("");
              setSelectedModification("");
              setSelectedCapacity("");
              setSelectedEngine("");
            }}
            disabled={!selectedYear || isLoadingOptions || isSubmitting}
            className="h-10 rounded-lg border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {isLoadingOptions ? tGarage("fields.make.loadingPlaceholder") : tGarage("fields.make.placeholder")}
            </option>
            {manufacturers.map((row) => (
              <option key={row.id} value={row.id}>
                {normalizeDisplayText(row.name)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {tGarage("fields.model.label")}
          <select
            value={selectedModelId}
            onChange={(event) => {
              setSelectedModelId(event.target.value);
              setSelectedModification("");
              setSelectedCapacity("");
              setSelectedEngine("");
            }}
            disabled={!selectedManufacturerId || isLoadingOptions || isSubmitting}
            className="h-10 rounded-lg border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {isLoadingOptions ? tGarage("fields.model.loadingPlaceholder") : tGarage("fields.model.placeholder")}
            </option>
            {models.map((row) => (
              <option key={row.id} value={row.id}>
                {normalizeDisplayText(row.name)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {tGarage("fields.modification.label")}
          <select
            value={selectedModification}
            onChange={(event) => {
              setSelectedModification(event.target.value);
              setSelectedCapacity("");
              setSelectedEngine("");
            }}
            disabled={!selectedModelId || isLoadingOptions || isSubmitting}
            className="h-10 rounded-lg border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {isLoadingOptions ? tGarage("fields.modification.loadingPlaceholder") : tGarage("fields.modification.placeholder")}
            </option>
            {modifications.map((row) => (
              <option key={row} value={row}>
                {normalizeDisplayText(row)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {tGarage("fields.capacity.label")}
          <select
            value={selectedCapacity}
            onChange={(event) => {
              setSelectedCapacity(event.target.value);
              setSelectedEngine("");
            }}
            disabled={!selectedModification || isLoadingOptions || isSubmitting}
            className="h-10 rounded-lg border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {isLoadingOptions ? tGarage("fields.capacity.loadingPlaceholder") : tGarage("fields.capacity.placeholder")}
            </option>
            {capacities.map((row) => (
              <option key={row} value={row}>
                {normalizeDisplayText(row)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {tGarage("fields.engine.label")}
          <select
            value={selectedEngine}
            onChange={(event) => setSelectedEngine(event.target.value)}
            disabled={!selectedCapacity || isLoadingOptions || isLoadingRows || isSubmitting}
            className="h-10 rounded-lg border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {isLoadingOptions || isLoadingRows ? tGarage("fields.engine.loadingPlaceholder") : tGarage("fields.engine.placeholder")}
            </option>
            {(engines.length ? engines : Array.from(new Set(matchingRows.map((row) => row.engine)))).map((row) => (
              <option key={row} value={row}>
                {normalizeDisplayText(row)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
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

        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-lg border disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          disabled={!canUseForFiltering || isSubmitting}
          onClick={() => {
            if (!selectedRow) {
              return;
            }
            onUseTemporaryAutoDb({
              manufacturerId: Number(selectedRow.manufacturer_id),
              modelId: Number(selectedRow.model_id),
              passangerCarId: Number(selectedRow.passanger_car_id),
            });
            showSuccess(t("new.messages.usedForFiltering"));
          }}
          aria-label={t("new.actions.useForFiltering")}
        >
          <Filter size={15} />
        </button>

        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-lg border disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          disabled={!canSave || isSubmitting}
          onClick={async () => {
            if (!selectedRow) {
              return;
            }
            setActiveSaveMode("save");
            try {
              await onSaveVehicle({
                year: selectedYear ? Number(selectedYear) : undefined,
                autodb_manufacturer_id: Number(selectedRow.manufacturer_id),
                autodb_model_id: Number(selectedRow.model_id),
                autodb_passanger_car_id: Number(selectedRow.passanger_car_id),
                autodb_vehicle_label: composedLabel,
                autodb_modification: selectedRow.modification,
                autodb_engine: selectedRow.engine,
                autodb_power_hp: parsePowerValue(selectedRow.hp),
                autodb_power_kw: parsePowerValue(selectedRow.kw),
                is_primary: isPrimary,
              });
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
      </div>

      {!isAuthenticated ? (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          {t("new.messages.authRequiredForSave")}
        </p>
      ) : null}
    </div>
  );
}

export function NewVehicleSelectionForm(props: NewVehicleSelectionFormProps) {
  return (
    <AutoDbSelectionForm
      isAuthenticated={props.isAuthenticated}
      onUseTemporaryAutoDb={props.onUseTemporaryAutoDb}
      onSaveVehicle={props.onSaveVehicle}
    />
  );
}
