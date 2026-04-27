"use client";

import { useEffect, useMemo, useState } from "react";

import type {
  BackofficeEmailSettings,
  BackofficeEmailSettingsPayload,
} from "@/features/backoffice/types/email-settings.types";

import {
  applyResendPreset,
  buildEmailSettingsPayload,
  EMPTY_STATE,
  type EmailProvider,
  type EmailSettingsFormState,
} from "./email-settings.constants";
import { EmailStatusCard } from "./email-status-card";
import { EmailTestPanel } from "./email-test-panel";
import { ResendPresetCard } from "./resend-preset-card";
import { SmtpSettingsForm } from "./smtp-settings-form";

function settingsToFormState(settings: BackofficeEmailSettings | null): EmailSettingsFormState {
  if (!settings) {
    return EMPTY_STATE;
  }
  const provider = settings.provider || "resend_smtp";
  const isResend = provider === "resend_smtp";
  return {
    provider,
    is_enabled: Boolean(settings.is_enabled),
    from_name: settings.from_name || (isResend ? "SVOM" : ""),
    from_email: settings.from_email || (isResend ? "no-reply@svom.com.ua" : ""),
    host: settings.host || (isResend ? "smtp.resend.com" : ""),
    port: String(settings.port || 587),
    host_user: settings.host_user || (isResend ? "resend" : ""),
    host_password: "",
    use_tls: Boolean(settings.use_tls),
    use_ssl: Boolean(settings.use_ssl),
    timeout: String(settings.timeout || 10),
    frontend_base_url: settings.frontend_base_url || (isResend ? "https://svom.com.ua" : ""),
  };
}

export function EmailSettingsForm({
  settings,
  isSaving,
  isTesting,
  onSave,
  onTest,
  t,
}: {
  settings: BackofficeEmailSettings | null;
  isSaving: boolean;
  isTesting: boolean;
  onSave: (payload: BackofficeEmailSettingsPayload) => Promise<unknown>;
  onTest: (recipient: string) => Promise<unknown>;
  t: (key: string) => string;
}) {
  const [form, setForm] = useState<EmailSettingsFormState>(EMPTY_STATE);
  const [testRecipient, setTestRecipient] = useState("");

  useEffect(() => {
    const next = settingsToFormState(settings);
    setForm(next.provider === "resend_smtp" ? applyResendPreset(next) : next);
  }, [settings]);

  const canSave = useMemo(() => {
    const port = Number(form.port);
    const timeout = Number(form.timeout);
    return !isSaving
      && form.from_email.trim().length > 0
      && form.host.trim().length > 0
      && Number.isFinite(port)
      && port > 0
      && Number.isFinite(timeout)
      && timeout > 0;
  }, [form.from_email, form.host, form.port, form.timeout, isSaving]);

  const canTest = useMemo(() => {
    return !isTesting && testRecipient.trim().length > 0;
  }, [isTesting, testRecipient]);

  const updateField = <K extends keyof EmailSettingsFormState>(key: K, value: EmailSettingsFormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const updateProvider = (provider: EmailProvider) => {
    setForm((current) => (
      provider === "resend_smtp"
        ? applyResendPreset(current)
        : { ...current, provider }
    ));
  };

  const submit = () => {
    void onSave(buildEmailSettingsPayload(form)).then(() => {
      setForm((current) => ({ ...current, host_password: "" }));
    });
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
      <div className="grid content-start gap-4">
        <ResendPresetCard provider={form.provider} onProviderChange={updateProvider} t={t} />
        <SmtpSettingsForm
          form={form}
          settings={settings}
          isSaving={isSaving}
          canSave={canSave}
          onSubmit={submit}
          onChange={updateField}
          t={t}
        />
      </div>

      <div className="grid content-start gap-4">
        <EmailTestPanel
          testRecipient={testRecipient}
          isTesting={isTesting}
          canTest={canTest}
          onRecipientChange={setTestRecipient}
          onTest={() => void onTest(testRecipient.trim())}
          t={t}
        />
        <EmailStatusCard settings={settings} t={t} />
      </div>
    </div>
  );
}
