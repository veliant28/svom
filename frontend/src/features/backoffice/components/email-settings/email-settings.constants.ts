import type { BackofficeEmailSettingsPayload } from "@/features/backoffice/types/email-settings.types";

export type EmailProvider = "resend_smtp" | "manual_smtp";

export type EmailSettingsFormState = {
  provider: EmailProvider;
  is_enabled: boolean;
  from_name: string;
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

export const RESEND_PRESET: Omit<EmailSettingsFormState, "host_password"> = {
  provider: "resend_smtp",
  is_enabled: true,
  from_name: "SVOM",
  from_email: "no-reply@svom.com.ua",
  host: "smtp.resend.com",
  port: "587",
  host_user: "resend",
  use_tls: true,
  use_ssl: false,
  timeout: "10",
  frontend_base_url: "https://svom.com.ua",
};

export const EMPTY_STATE: EmailSettingsFormState = {
  provider: "resend_smtp",
  is_enabled: false,
  from_name: "SVOM",
  from_email: "no-reply@svom.com.ua",
  host: "smtp.resend.com",
  port: "587",
  host_user: "resend",
  host_password: "",
  use_tls: true,
  use_ssl: false,
  timeout: "10",
  frontend_base_url: "https://svom.com.ua",
};

export function applyResendPreset(current: EmailSettingsFormState): EmailSettingsFormState {
  return {
    ...current,
    ...RESEND_PRESET,
    host_password: current.host_password,
  };
}

export function buildEmailSettingsPayload(form: EmailSettingsFormState): BackofficeEmailSettingsPayload {
  const payload: BackofficeEmailSettingsPayload = {
    provider: form.provider,
    is_enabled: form.is_enabled,
    from_name: form.from_name.trim(),
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
  return payload;
}
