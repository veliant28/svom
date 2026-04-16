"use client";

import { Loader2, PlusCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { createGarageVehicle } from "@/features/garage/api/create-garage-vehicle";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useVehicleCascade } from "@/features/garage/hooks/use-vehicle-cascade";
import { isApiRequestError } from "@/shared/api/http-client";

type GarageAddVehicleFormProps = {
  onCreated: () => Promise<void> | void;
};

type SubmitState = "idle" | "success" | "error";

function formatEngineLabel(
  engine: {
    engine: string;
    power_hp: number | null;
    power_kw: number | null;
  },
): string {
  const powerLabel = [
    engine.power_hp ? `${engine.power_hp} л.с.` : "",
    engine.power_kw ? `${engine.power_kw} кВт` : "",
  ]
    .filter(Boolean)
    .join(" / ");

  return [engine.engine, powerLabel].filter(Boolean).join(" · ");
}

function getApiErrorText(error: unknown): string | null {
  if (!isApiRequestError(error)) {
    return null;
  }

  const payload = error.payload;
  if (!payload || typeof payload !== "object") {
    return error.message || null;
  }

  const detail = payload.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }

  const message = payload.message;
  if (typeof message === "string" && message.trim()) {
    return message.trim();
  }

  for (const value of Object.values(payload)) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
    if (Array.isArray(value)) {
      const firstString = value.find((item) => typeof item === "string" && item.trim());
      if (typeof firstString === "string") {
        return firstString.trim();
      }
    }
  }

  return error.message || null;
}

export function GarageAddVehicleForm({ onCreated }: GarageAddVehicleFormProps) {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const { token, isAuthenticated } = useAuth();
  const t = useTranslations("garage.form");
  const {
    selectedYear,
    selectedMake,
    selectedModel,
    selectedModification,
    selectedCapacity,
    selectedEngine,
    setSelectedYear,
    setSelectedMake,
    setSelectedModel,
    setSelectedModification,
    setSelectedCapacity,
    setSelectedEngine,
    years,
    makes,
    models,
    modifications,
    capacities,
    engines,
    isLoadingYears,
    isLoadingMakes,
    isLoadingModels,
    isLoadingModifications,
    isLoadingCapacities,
    isLoadingEngines,
  } = useVehicleCascade();

  const [isPrimary, setIsPrimary] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitState, setSubmitState] = useState<SubmitState>("idle");
  const [submitErrorText, setSubmitErrorText] = useState<string | null>(null);

  const isSubmitDisabled = useMemo(
    () =>
      !isAuthenticated ||
      !token ||
      isSubmitting ||
      isLoadingEngines ||
      !selectedMake ||
      !selectedModel ||
      !selectedModification ||
      !selectedCapacity ||
      !selectedEngine,
    [
      isAuthenticated,
      token,
      isSubmitting,
      isLoadingEngines,
      selectedMake,
      selectedModel,
      selectedModification,
      selectedCapacity,
      selectedEngine,
    ],
  );

  if (!isMounted) {
    return (
      <section
        className="min-w-0 overflow-hidden rounded-xl border p-4"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        <h2 className="text-lg font-semibold">{t("title")}</h2>
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
          {t("subtitle")}
        </p>
        <div className="mt-4 h-10 animate-pulse rounded-md border" style={{ borderColor: "var(--border)" }} />
      </section>
    );
  }

  return (
    <section
      className="min-w-0 overflow-hidden rounded-xl border p-4"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
    >
      <h2 className="text-lg font-semibold">{t("title")}</h2>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {t("subtitle")}
      </p>
      {!isAuthenticated ? (
        <p className="mt-2 text-xs" style={{ color: "var(--danger, #b42318)" }}>
          {t("messages.authRequired")}
        </p>
      ) : null}

      <form
        className="mt-4 grid min-w-0 max-w-full gap-3"
        onSubmit={async (event) => {
          event.preventDefault();
          if (isSubmitDisabled) {
            return;
          }

          setSubmitState("idle");
          setSubmitErrorText(null);
          setIsSubmitting(true);

          try {
            if (!token) {
              throw new Error("No auth token");
            }
            await createGarageVehicle(token, {
              car_modification: Number(selectedEngine),
              is_primary: isPrimary,
            });
            setSubmitState("success");
            setSelectedMake("");
            setSelectedModel("");
            setSelectedYear("");
            setSelectedModification("");
            setSelectedCapacity("");
            setSelectedEngine("");
            setIsPrimary(false);
            await onCreated();
          } catch (error) {
            setSubmitErrorText(getApiErrorText(error));
            setSubmitState("error");
          } finally {
            setIsSubmitting(false);
          }
        }}
      >
        <label className="flex min-w-0 flex-col gap-1 text-xs">
          {t("fields.year.label")}
          <select
            value={selectedYear}
            onChange={(event) => setSelectedYear(event.target.value)}
            disabled={isLoadingYears || isSubmitting}
            className="h-10 w-full max-w-full min-w-0 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {isLoadingYears ? t("fields.year.loadingPlaceholder") : t("fields.year.anyOption")}
            </option>
            {years.map((year) => (
              <option key={year.year} value={year.year}>
                {year.year}
              </option>
            ))}
          </select>
        </label>

        <label className="flex min-w-0 flex-col gap-1 text-xs">
          {t("fields.make.label")}
          <select
            value={selectedMake}
            onChange={(event) => setSelectedMake(event.target.value)}
            disabled={isLoadingMakes || isSubmitting}
            className="h-10 w-full max-w-full min-w-0 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {isLoadingMakes ? t("fields.make.loadingPlaceholder") : t("fields.make.placeholder")}
            </option>
            {makes.map((make) => (
              <option key={make.id} value={make.id}>
                {make.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex min-w-0 flex-col gap-1 text-xs">
          {t("fields.model.label")}
          <select
            value={selectedModel}
            onChange={(event) => setSelectedModel(event.target.value)}
            disabled={!selectedMake || isLoadingModels || isSubmitting}
            className="h-10 w-full max-w-full min-w-0 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {isLoadingModels ? t("fields.model.loadingPlaceholder") : t("fields.model.placeholder")}
            </option>
            {models.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex min-w-0 flex-col gap-1 text-xs">
          {t("fields.modification.label")}
          <select
            value={selectedModification}
            onChange={(event) => setSelectedModification(event.target.value)}
            disabled={!selectedModel || isLoadingModifications || isSubmitting}
            className="h-10 w-full max-w-full min-w-0 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {isLoadingModifications ? t("fields.modification.loadingPlaceholder") : t("fields.modification.placeholder")}
            </option>
            {modifications.map((modification) => (
              <option key={modification.modification} value={modification.modification}>
                {modification.modification}
              </option>
            ))}
          </select>
        </label>

        <label className="flex min-w-0 flex-col gap-1 text-xs">
          {t("fields.capacity.label")}
          <select
            value={selectedCapacity}
            onChange={(event) => setSelectedCapacity(event.target.value)}
            disabled={!selectedModification || isLoadingCapacities || isSubmitting}
            className="h-10 w-full max-w-full min-w-0 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {isLoadingCapacities ? t("fields.capacity.loadingPlaceholder") : t("fields.capacity.placeholder")}
            </option>
            {capacities.map((capacity) => (
              <option key={capacity.capacity} value={capacity.capacity}>
                {capacity.capacity}
              </option>
            ))}
          </select>
        </label>

        <label className="flex min-w-0 flex-col gap-1 text-xs">
          {t("fields.engine.label")}
          <select
            value={selectedEngine}
            onChange={(event) => setSelectedEngine(event.target.value)}
            disabled={!selectedCapacity || isLoadingEngines || isSubmitting}
            className="h-10 w-full max-w-full min-w-0 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">
              {isLoadingEngines ? t("fields.engine.loadingPlaceholder") : t("fields.engine.placeholder")}
            </option>
            {engines.map((engine) => (
              <option key={engine.id} value={engine.id}>
                {formatEngineLabel(engine)}
              </option>
            ))}
          </select>
        </label>

        <label className="inline-flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={isPrimary}
            onChange={(event) => setIsPrimary(event.target.checked)}
            disabled={isSubmitting}
          />
          {t("fields.isPrimary")}
        </label>

        <button
          type="submit"
          disabled={isSubmitDisabled}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          {isSubmitting ? <Loader2 size={15} className="animate-spin" /> : <PlusCircle size={15} />}
          {isSubmitting ? t("actions.submitting") : t("actions.submit")}
        </button>
      </form>

      {submitState !== "idle" ? (
        <p
          className="mt-3 text-xs"
          style={{ color: submitState === "success" ? "var(--success, #136f3a)" : "var(--danger, #b42318)" }}
        >
          {submitState === "success" ? t("messages.success") : submitErrorText || t("messages.error")}
        </p>
      ) : null}
    </section>
  );
}
