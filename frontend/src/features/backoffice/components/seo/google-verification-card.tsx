"use client";

import { Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { BackofficeGoogleSettings } from "@/features/backoffice/api/seo-api.types";

type VerificationForm = Pick<
BackofficeGoogleSettings,
  "search_console_verification_token" | "google_site_verification_meta"
>;

function toForm(settings: BackofficeGoogleSettings | null): VerificationForm {
  return {
    search_console_verification_token: settings?.search_console_verification_token ?? "",
    google_site_verification_meta: settings?.google_site_verification_meta ?? "",
  };
}

export function GoogleVerificationCard({
  settings,
  isSaving,
  canManage,
  onSave,
  t,
}: {
  settings: BackofficeGoogleSettings | null;
  isSaving: boolean;
  canManage: boolean;
  onSave: (payload: Partial<BackofficeGoogleSettings>) => Promise<BackofficeGoogleSettings | null>;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  const [form, setForm] = useState<VerificationForm>(() => toForm(settings));

  useEffect(() => {
    setForm(toForm(settings));
  }, [settings]);

  const isDirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(toForm(settings)), [form, settings]);

  return (
    <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{t("seo.google.verificationTitle")}</p>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("seo.google.verificationHint")}</p>
        </div>
        {canManage ? (
          <button
            type="button"
            disabled={!isDirty || isSaving}
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
        <Field
          label={t("seo.fields.searchConsoleVerificationToken")}
          value={form.search_console_verification_token}
          disabled={!canManage}
          onChange={(next) => setForm((prev) => ({ ...prev, search_console_verification_token: next }))}
        />
        <Field
          label={t("seo.fields.googleSiteVerificationMeta")}
          value={form.google_site_verification_meta}
          disabled={!canManage}
          onChange={(next) => setForm((prev) => ({ ...prev, google_site_verification_meta: next }))}
        />
      </div>
    </section>
  );
}

function Field({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  disabled: boolean;
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
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      />
    </label>
  );
}
