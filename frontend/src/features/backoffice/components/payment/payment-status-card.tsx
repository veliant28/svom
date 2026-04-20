import type { BackofficeMonobankSettings } from "@/features/backoffice/types/payment.types";

export function PaymentStatusCard({
  settings,
  t,
}: {
  settings: BackofficeMonobankSettings | null;
  t: (key: string) => string;
}) {
  return (
    <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{t("payments.monobank.status")}</p>
      <div className="mt-3 grid gap-2 text-xs">
        <p><span style={{ color: "var(--muted)" }}>{t("payments.monobank.enabled")}: </span>{settings?.is_enabled ? t("yes") : t("no")}</p>
        <p><span style={{ color: "var(--muted)" }}>{t("payments.monobank.lastConnection")}: </span>{settings?.last_connection_checked_at || "-"}</p>
        <p><span style={{ color: "var(--muted)" }}>{t("payments.monobank.lastConnectionState")}: </span>{settings?.last_connection_ok === null ? "-" : settings?.last_connection_ok ? t("statuses.ok") : t("statuses.failed")}</p>
        <p><span style={{ color: "var(--muted)" }}>{t("payments.monobank.lastConnectionMessage")}: </span>{settings?.last_connection_message || "-"}</p>
      </div>
    </div>
  );
}
