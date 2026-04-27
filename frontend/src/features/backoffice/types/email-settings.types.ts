export type BackofficeEmailSettings = {
  provider: "resend_smtp" | "manual_smtp";
  is_enabled: boolean;
  from_name: string;
  from_email: string;
  host: string;
  port: number;
  host_user: string;
  host_password_masked: string;
  use_tls: boolean;
  use_ssl: boolean;
  timeout: number;
  frontend_base_url: string;
  last_connection_checked_at: string | null;
  last_connection_ok: boolean | null;
  last_connection_message: string;
};

export type BackofficeEmailSettingsPayload = Partial<{
  provider: "resend_smtp" | "manual_smtp";
  is_enabled: boolean;
  from_name: string;
  from_email: string;
  host: string;
  port: number;
  host_user: string;
  host_password: string;
  use_tls: boolean;
  use_ssl: boolean;
  timeout: number;
  frontend_base_url: string;
}>;

export type BackofficeEmailTestResult = {
  ok: boolean;
  message: string;
};
