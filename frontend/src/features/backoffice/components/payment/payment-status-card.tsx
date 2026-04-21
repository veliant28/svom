import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";

export function PaymentStatusCard({
  settings,
  title,
  enabledLabel,
  lastConnectionLabel,
  lastConnectionStateLabel,
  lastConnectionMessageLabel,
  t,
}: {
  settings: {
    is_enabled?: boolean;
    last_connection_checked_at?: string | null;
    last_connection_ok?: boolean | null;
    last_connection_message?: string;
  } | null;
  title: string;
  enabledLabel: string;
  lastConnectionLabel: string;
  lastConnectionStateLabel: string;
  lastConnectionMessageLabel: string;
  t: (key: string) => string;
}) {
  const connectionState = settings?.last_connection_ok === null
    ? "-"
    : settings?.last_connection_ok
      ? t("statuses.ok")
      : t("statuses.failed");

  return (
    <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{title}</p>
      <div className="mt-3 grid gap-2 text-xs">
        <div className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <p style={{ color: "var(--muted)" }}>{enabledLabel}</p>
          <p className="mt-0.5 font-semibold">{settings?.is_enabled ? t("yes") : t("no")}</p>
        </div>
        <div className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <p style={{ color: "var(--muted)" }}>{lastConnectionLabel}</p>
          <p className="mt-0.5 font-semibold">{formatBackofficeDate(settings?.last_connection_checked_at || null)}</p>
        </div>
        <div className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <p style={{ color: "var(--muted)" }}>{lastConnectionStateLabel}</p>
          <p className="mt-0.5 font-semibold">{connectionState}</p>
        </div>
        <div className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <p style={{ color: "var(--muted)" }}>{lastConnectionMessageLabel}</p>
          <p className="mt-0.5 break-words font-semibold">{settings?.last_connection_message || "-"}</p>
        </div>
      </div>
    </div>
  );
}
