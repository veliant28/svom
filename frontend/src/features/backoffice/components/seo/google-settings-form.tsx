"use client";

import { Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { BackofficeGoogleSettings } from "@/features/backoffice/api/seo-api.types";

function toForm(settings: BackofficeGoogleSettings | null): BackofficeGoogleSettings {
  return {
    is_enabled: settings?.is_enabled ?? false,
    ga4_measurement_id: settings?.ga4_measurement_id ?? "",
    gtm_container_id: settings?.gtm_container_id ?? "",
    search_console_verification_token: settings?.search_console_verification_token ?? "",
    google_site_verification_meta: settings?.google_site_verification_meta ?? "",
    consent_mode_enabled: settings?.consent_mode_enabled ?? false,
    ecommerce_events_enabled: settings?.ecommerce_events_enabled ?? true,
    debug_mode: settings?.debug_mode ?? false,
    anonymize_ip: settings?.anonymize_ip ?? true,
    updated_at: settings?.updated_at ?? "",
  };
}

export function GoogleSettingsForm({
  settings,
  isSaving,
  canManage,
  fieldErrors,
  onSave,
  t,
}: {
  settings: BackofficeGoogleSettings | null;
  isSaving: boolean;
  canManage: boolean;
  fieldErrors: Partial<Record<"ga4_measurement_id" | "gtm_container_id", string>>;
  onSave: (payload: Partial<BackofficeGoogleSettings>) => Promise<BackofficeGoogleSettings | null>;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  const [form, setForm] = useState<BackofficeGoogleSettings>(() => toForm(settings));

  useEffect(() => {
    setForm(toForm(settings));
  }, [settings]);

  const isDirty = useMemo(() => {
    const baseline = toForm(settings);
    return JSON.stringify(baseline) !== JSON.stringify(form);
  }, [form, settings]);
  const ga4Invalid = Boolean(form.ga4_measurement_id.trim()) && !/^G-[A-Z0-9]+$/i.test(form.ga4_measurement_id.trim());
  const gtmInvalid = Boolean(form.gtm_container_id.trim()) && !/^GTM-[A-Z0-9]+$/i.test(form.gtm_container_id.trim());
  const ga4Error = ga4Invalid ? t("seo.messages.invalidGa4Id") : fieldErrors.ga4_measurement_id;
  const gtmError = gtmInvalid ? t("seo.messages.invalidGtmId") : fieldErrors.gtm_container_id;
  const canSubmit = isDirty && !isSaving && !ga4Invalid && !gtmInvalid;

  return (
    <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{t("seo.google.settingsTitle")}</p>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("seo.google.settingsHint")}</p>
        </div>
        {canManage ? (
          <button
            type="button"
            disabled={!canSubmit}
            className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
            onClick={() => {
              void onSave(form);
            }}
          >
            <Save size={13} />
            {isSaving ? t("seo.actions.saving") : t("seo.actions.save")}
          </button>
        ) : null}
      </div>

      <div className="grid gap-3">
        <ToggleField label={t("seo.fields.enabled")} checked={form.is_enabled} disabled={!canManage} onToggle={() => setForm((prev) => ({ ...prev, is_enabled: !prev.is_enabled }))} />
        <ToggleField label={t("seo.fields.consentModeEnabled")} checked={form.consent_mode_enabled} disabled={!canManage} onToggle={() => setForm((prev) => ({ ...prev, consent_mode_enabled: !prev.consent_mode_enabled }))} />
        <ToggleField label={t("seo.fields.ecommerceEventsEnabled")} checked={form.ecommerce_events_enabled} disabled={!canManage} onToggle={() => setForm((prev) => ({ ...prev, ecommerce_events_enabled: !prev.ecommerce_events_enabled }))} />
        <ToggleField label={t("seo.fields.debugMode")} checked={form.debug_mode} disabled={!canManage} onToggle={() => setForm((prev) => ({ ...prev, debug_mode: !prev.debug_mode }))} />
        <ToggleField label={t("seo.fields.anonymizeIp")} checked={form.anonymize_ip} disabled={!canManage} onToggle={() => setForm((prev) => ({ ...prev, anonymize_ip: !prev.anonymize_ip }))} />

        <InputField
          label={t("seo.fields.ga4MeasurementId")}
          value={form.ga4_measurement_id}
          disabled={!canManage}
          error={ga4Error}
          onChange={(next) => setForm((prev) => ({ ...prev, ga4_measurement_id: next }))}
        />
        <InputField
          label={t("seo.fields.gtmContainerId")}
          value={form.gtm_container_id}
          disabled={!canManage}
          error={gtmError}
          onChange={(next) => setForm((prev) => ({ ...prev, gtm_container_id: next }))}
        />
      </div>
    </section>
  );
}

function ToggleField({
  label,
  checked,
  disabled,
  onToggle,
}: {
  label: string;
  checked: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  return (
    <label className="inline-flex items-center gap-2 text-sm font-medium">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={onToggle} />
      <span>{label}</span>
    </label>
  );
}

function InputField({
  label,
  value,
  disabled,
  error,
  onChange,
}: {
  label: string;
  value: string;
  disabled: boolean;
  error?: string;
  onChange: (next: string) => void;
}) {
  return (
    <label className="grid gap-1">
      <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <input
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 rounded-md border px-3 text-sm"
        style={{ borderColor: error ? "#fca5a5" : "var(--border)", backgroundColor: "var(--surface-2)" }}
      />
      {error ? <span className="text-xs" style={{ color: "#b91c1c" }}>{error}</span> : null}
    </label>
  );
}
