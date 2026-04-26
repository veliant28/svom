"use client";

import { useEffect, useMemo, useState } from "react";
import { MailCheck, Minus, Plus, Save } from "lucide-react";

import type {
  BackofficeEmailSettings,
  BackofficeEmailSettingsPayload,
  BackofficeEmailTestResult,
} from "@/features/backoffice/types/email-settings.types";

type EmailSettingsFormState = {
  is_enabled: boolean;
  from_email: string;
  host: string;
  port: string;
  host_user: string;
  host_password: string;
  use_tls: boolean;
  use_ssl: boolean;
  timeout: string;
  frontend_base_url: string;
};

const EMPTY_STATE: EmailSettingsFormState = {
  is_enabled: false,
  from_email: "",
  host: "",
  port: "587",
  host_user: "",
  host_password: "",
  use_tls: true,
  use_ssl: false,
  timeout: "10",
  frontend_base_url: "",
};

function formatDate(value: string | null): string {
  if (!value) {
    return "";
  }
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function stepNumberValue(value: string, delta: number, min: number): string {
  const parsed = Number(value);
  const current = Number.isFinite(parsed) && parsed >= min ? parsed : min;
  return String(Math.max(min, current + delta));
}

function normalizeNumberInput(value: string): string {
  return value.replace(/\D/g, "");
}

function NumberStepperField({
  label,
  value,
  min = 1,
  step = 1,
  onChange,
}: {
  label: string;
  value: string;
  min?: number;
  step?: number;
  onChange: (next: string) => void;
}) {
  return (
    <div className="inline-grid w-fit gap-1 text-xs">
      <span>{label}</span>
      <div
        className="inline-flex h-9 w-fit items-center rounded-full border px-1"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      >
        <button
          type="button"
          className="inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors hover:opacity-90"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          aria-label={`${label} -`}
          onClick={() => onChange(stepNumberValue(value, -step, min))}
        >
          <Minus className="h-3.5 w-3.5" />
        </button>
        <input
          type="text"
          inputMode="numeric"
          autoComplete="off"
          value={value}
          aria-label={label}
          className="h-7 w-16 border-0 bg-transparent px-1 text-center text-sm font-semibold outline-none"
          onChange={(event) => onChange(normalizeNumberInput(event.target.value))}
          onKeyDown={(event) => {
            if (event.key === "ArrowUp") {
              event.preventDefault();
              onChange(stepNumberValue(value, step, min));
            } else if (event.key === "ArrowDown") {
              event.preventDefault();
              onChange(stepNumberValue(value, -step, min));
            }
          }}
        />
        <button
          type="button"
          className="inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors hover:opacity-90"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          aria-label={`${label} +`}
          onClick={() => onChange(stepNumberValue(value, step, min))}
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

export function EmailSettingsForm({
  settings,
  testResult,
  isSaving,
  isTesting,
  onSave,
  onTest,
  t,
}: {
  settings: BackofficeEmailSettings | null;
  testResult: BackofficeEmailTestResult | null;
  isSaving: boolean;
  isTesting: boolean;
  onSave: (payload: BackofficeEmailSettingsPayload) => Promise<unknown>;
  onTest: (recipient: string) => Promise<unknown>;
  t: (key: string) => string;
}) {
  const [form, setForm] = useState<EmailSettingsFormState>(EMPTY_STATE);
  const [testRecipient, setTestRecipient] = useState("");

  useEffect(() => {
    if (!settings) {
      setForm(EMPTY_STATE);
      return;
    }
    setForm({
      is_enabled: Boolean(settings.is_enabled),
      from_email: settings.from_email || "",
      host: settings.host || "",
      port: String(settings.port || 587),
      host_user: settings.host_user || "",
      host_password: "",
      use_tls: Boolean(settings.use_tls),
      use_ssl: Boolean(settings.use_ssl),
      timeout: String(settings.timeout || 10),
      frontend_base_url: settings.frontend_base_url || "",
    });
  }, [settings]);

  const canSave = useMemo(() => {
    const port = Number(form.port);
    const timeout = Number(form.timeout);
    return !isSaving && Number.isFinite(port) && port > 0 && Number.isFinite(timeout) && timeout > 0;
  }, [form.port, form.timeout, isSaving]);

  const canTest = useMemo(() => {
    return !isTesting && testRecipient.trim().length > 0;
  }, [isTesting, testRecipient]);

  const updateField = <K extends keyof EmailSettingsFormState>(key: K, value: EmailSettingsFormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const lastCheckedAt = formatDate(settings?.last_connection_checked_at || null);
  const statusLabel = settings?.last_connection_ok === true
    ? t("email.status.ok")
    : settings?.last_connection_ok === false
      ? t("email.status.failed")
      : t("email.status.notChecked");

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
      <form
        className="rounded-xl border p-4"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        onSubmit={(event) => {
          event.preventDefault();
          const payload: BackofficeEmailSettingsPayload = {
            is_enabled: form.is_enabled,
            from_email: form.from_email.trim(),
            host: form.host.trim(),
            port: Number(form.port) || 587,
            host_user: form.host_user.trim(),
            use_tls: form.use_tls,
            use_ssl: form.use_ssl,
            timeout: Number(form.timeout) || 10,
            frontend_base_url: form.frontend_base_url.trim(),
          };
          if (form.host_password.trim()) {
            payload.host_password = form.host_password.trim();
          }
          void onSave(payload).then(() => {
            setForm((current) => ({ ...current, host_password: "" }));
          });
        }}
      >
        <div className="flex items-start gap-3">
          <span
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md"
            style={{ backgroundColor: "var(--surface-2)", color: "var(--foreground)" }}
          >
            <MailCheck size={18} />
          </span>
          <div>
            <p className="text-sm font-semibold">{t("email.form.title")}</p>
            <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
              {t("email.form.helper")}
            </p>
          </div>
        </div>

        <div className="mt-4 grid gap-3">
          <label className="inline-flex items-center gap-2 text-xs font-medium">
            <input
              type="checkbox"
              checked={form.is_enabled}
              onChange={(event) => updateField("is_enabled", event.target.checked)}
            />
            {t("email.fields.enabled")}
          </label>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs">
              {t("email.fields.fromEmail")}
              <input
                type="email"
                value={form.from_email}
                onChange={(event) => updateField("from_email", event.target.value)}
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs">
              {t("email.fields.host")}
              <input
                value={form.host}
                onChange={(event) => updateField("host", event.target.value)}
                placeholder="smtp.example.com"
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              />
            </label>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs">
              {t("email.fields.frontendBaseUrl")}
              <input
                value={form.frontend_base_url}
                onChange={(event) => updateField("frontend_base_url", event.target.value)}
                placeholder="https://example.com"
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <NumberStepperField
                label={t("email.fields.port")}
                value={form.port}
                onChange={(next) => updateField("port", next)}
              />
              <NumberStepperField
                label={t("email.fields.timeout")}
                value={form.timeout}
                onChange={(next) => updateField("timeout", next)}
              />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs">
              {t("email.fields.hostUser")}
              <input
                value={form.host_user}
                onChange={(event) => updateField("host_user", event.target.value)}
                autoComplete="username"
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs">
              {t("email.fields.hostPassword")}
              <input
                type="password"
                value={form.host_password}
                onChange={(event) => updateField("host_password", event.target.value)}
                placeholder={settings?.host_password_masked || "********"}
                autoComplete="new-password"
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              />
              {settings?.host_password_masked ? (
                <span style={{ color: "var(--muted)" }}>
                  {t("email.fields.savedPassword")}: {settings.host_password_masked}
                </span>
              ) : null}
            </label>
          </div>

          <div className="flex flex-wrap gap-4 text-xs">
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.use_tls}
                onChange={(event) => updateField("use_tls", event.target.checked)}
              />
              {t("email.fields.useTls")}
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.use_ssl}
                onChange={(event) => updateField("use_ssl", event.target.checked)}
              />
              {t("email.fields.useSsl")}
            </label>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="submit"
              disabled={!canSave}
              className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
              style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
            >
              <Save size={13} />
              {isSaving ? t("email.actions.saving") : t("email.actions.save")}
            </button>
          </div>
        </div>
      </form>

      <div className="grid content-start gap-4">
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <p className="text-sm font-semibold">{t("email.test.title")}</p>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("email.test.helper")}</p>
          <div className="mt-3 grid gap-3">
            <label className="flex flex-col gap-1 text-xs">
              {t("email.test.recipient")}
              <input
                type="email"
                value={testRecipient}
                onChange={(event) => setTestRecipient(event.target.value)}
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              />
            </label>
            <button
              type="button"
              disabled={!canTest}
              onClick={() => void onTest(testRecipient.trim())}
              className="rounded-md border px-3 py-2 text-xs font-semibold disabled:opacity-60"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            >
              {isTesting ? t("email.actions.testing") : t("email.actions.test")}
            </button>
            {testResult ? (
              <p className="text-xs" style={{ color: testResult.ok ? "var(--success, #136f3a)" : "#b91c1c" }}>
                {testResult.message}
              </p>
            ) : null}
          </div>
        </div>

        <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <p className="text-sm font-semibold">{t("email.status.title")}</p>
          <dl className="mt-3 grid gap-2 text-xs">
            <div className="flex items-center justify-between gap-3">
              <dt style={{ color: "var(--muted)" }}>{t("email.status.enabled")}</dt>
              <dd className="font-semibold">{settings?.is_enabled ? t("yes") : t("no")}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt style={{ color: "var(--muted)" }}>{t("email.status.connection")}</dt>
              <dd className="font-semibold">{statusLabel}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt style={{ color: "var(--muted)" }}>{t("email.status.lastChecked")}</dt>
              <dd className="font-semibold">{lastCheckedAt || "—"}</dd>
            </div>
            <div className="grid gap-1">
              <dt style={{ color: "var(--muted)" }}>{t("email.status.message")}</dt>
              <dd className="break-words font-semibold">{settings?.last_connection_message || "—"}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
