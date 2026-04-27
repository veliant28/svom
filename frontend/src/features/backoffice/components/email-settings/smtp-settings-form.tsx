import { MailCheck, Save } from "lucide-react";

import type { BackofficeEmailSettings } from "@/features/backoffice/types/email-settings.types";

import type { EmailSettingsFormState } from "./email-settings.constants";
import { NumberStepperField } from "./number-stepper-field";

export function SmtpSettingsForm({
  form,
  settings,
  isSaving,
  canSave,
  onSubmit,
  onChange,
  t,
}: {
  form: EmailSettingsFormState;
  settings: BackofficeEmailSettings | null;
  isSaving: boolean;
  canSave: boolean;
  onSubmit: () => void;
  onChange: <K extends keyof EmailSettingsFormState>(key: K, value: EmailSettingsFormState[K]) => void;
  t: (key: string) => string;
}) {
  const isResend = form.provider === "resend_smtp";

  return (
    <form
      className="rounded-lg border p-4"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
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
            onChange={(event) => onChange("is_enabled", event.target.checked)}
          />
          {t("email.fields.enabled")}
        </label>

        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs">
            {t("email.fields.fromName")}
            <input
              value={form.from_name}
              onChange={(event) => onChange("from_name", event.target.value)}
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            {t("email.fields.fromEmail")}
            <input
              type="email"
              value={form.from_email}
              onChange={(event) => onChange("from_email", event.target.value)}
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
            <span style={{ color: "var(--muted)" }}>{t("email.hints.fromEmail")}</span>
          </label>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs">
            {t("email.fields.host")}
            <input
              value={form.host}
              disabled={isResend}
              onChange={(event) => onChange("host", event.target.value)}
              placeholder="smtp.example.com"
              className="h-10 rounded-md border px-3 disabled:opacity-70"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            {t("email.fields.frontendBaseUrl")}
            <input
              value={form.frontend_base_url}
              onChange={(event) => onChange("frontend_base_url", event.target.value)}
              placeholder="https://example.com"
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
          </label>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs">
            {t("email.fields.hostUser")}
            <input
              value={form.host_user}
              disabled={isResend}
              onChange={(event) => onChange("host_user", event.target.value)}
              autoComplete="username"
              className="h-10 rounded-md border px-3 disabled:opacity-70"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            {t("email.fields.hostPassword")}
            <input
              type="password"
              value={form.host_password}
              onChange={(event) => onChange("host_password", event.target.value)}
              placeholder={settings?.host_password_masked || "********"}
              autoComplete="new-password"
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
            <span style={{ color: "var(--muted)" }}>{t("email.hints.hostPassword")}</span>
            {settings?.host_password_masked ? (
              <span style={{ color: "var(--muted)" }}>
                {t("email.fields.savedPassword")}: {settings.host_password_masked}
              </span>
            ) : null}
          </label>
        </div>

        <div className="grid gap-3 md:grid-cols-[auto_1fr]">
          <div className="grid gap-3 sm:grid-cols-2">
            <NumberStepperField
              label={t("email.fields.port")}
              value={form.port}
              disabled={isResend}
              onChange={(next) => onChange("port", next)}
            />
            <NumberStepperField
              label={t("email.fields.timeout")}
              value={form.timeout}
              disabled={isResend}
              onChange={(next) => onChange("timeout", next)}
            />
          </div>
          <div className="flex flex-wrap items-end gap-4 text-xs">
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.use_tls}
                disabled={isResend}
                onChange={(event) => onChange("use_tls", event.target.checked)}
              />
              {t("email.fields.useTls")}
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.use_ssl}
                disabled={isResend}
                onChange={(event) => onChange("use_ssl", event.target.checked)}
              />
              {t("email.fields.useSsl")}
            </label>
          </div>
        </div>

        <button
          type="submit"
          disabled={!canSave}
          className="inline-flex h-10 w-fit items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
          style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
        >
          <Save size={13} />
          {isSaving ? t("email.actions.saving") : t("email.actions.save")}
        </button>
      </div>
    </form>
  );
}
