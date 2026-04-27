import type { BackofficeEmailSettings } from "@/features/backoffice/types/email-settings.types";

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

export function EmailStatusCard({
  settings,
  t,
}: {
  settings: BackofficeEmailSettings | null;
  t: (key: string) => string;
}) {
  const lastCheckedAt = formatDate(settings?.last_connection_checked_at || null);
  const statusLabel = settings?.last_connection_ok === true
    ? t("email.status.ok")
    : settings?.last_connection_ok === false
      ? t("email.status.failed")
      : t("email.status.notChecked");

  return (
    <div className="rounded-lg border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{t("email.status.title")}</p>
      <dl className="mt-3 grid gap-2 text-xs">
        <div className="flex items-center justify-between gap-3">
          <dt style={{ color: "var(--muted)" }}>{t("email.status.enabled")}</dt>
          <dd className="font-semibold">{settings?.is_enabled ? t("yes") : t("no")}</dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt style={{ color: "var(--muted)" }}>{t("email.status.provider")}</dt>
          <dd className="font-semibold">
            {settings?.provider === "manual_smtp" ? t("email.provider.manual") : t("email.provider.resend")}
          </dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt style={{ color: "var(--muted)" }}>{t("email.status.connection")}</dt>
          <dd className="font-semibold">{statusLabel}</dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt style={{ color: "var(--muted)" }}>{t("email.status.lastChecked")}</dt>
          <dd className="font-semibold">{lastCheckedAt || "-"}</dd>
        </div>
      </dl>
    </div>
  );
}
