import { AlertTriangle, CheckCircle2, Info, SlidersHorizontal } from "lucide-react";

import type { EmailProvider } from "./email-settings.constants";

export function ResendPresetCard({
  provider,
  onProviderChange,
  t,
}: {
  provider: EmailProvider;
  onProviderChange: (provider: EmailProvider) => void;
  t: (key: string) => string;
}) {
  return (
    <div className="rounded-lg border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="flex items-start gap-3">
        <span
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md"
          style={{ backgroundColor: "var(--surface-2)", color: "var(--foreground)" }}
        >
          <Info size={18} />
        </span>
        <div>
          <p className="text-sm font-semibold">{t("email.provider.title")}</p>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
            {t("email.provider.helper")}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => onProviderChange("resend_smtp")}
          className="rounded-lg border p-3 text-left text-xs font-semibold transition-colors"
          style={{
            borderColor: provider === "resend_smtp" ? "#2563eb" : "var(--border)",
            backgroundColor: provider === "resend_smtp" ? "rgba(37, 99, 235, 0.10)" : "var(--surface-2)",
          }}
        >
          <span className="flex items-center gap-2">
            <CheckCircle2 size={15} />
            {t("email.provider.resend")}
          </span>
        </button>
        <button
          type="button"
          onClick={() => onProviderChange("manual_smtp")}
          className="rounded-lg border p-3 text-left text-xs font-semibold transition-colors"
          style={{
            borderColor: provider === "manual_smtp" ? "#2563eb" : "var(--border)",
            backgroundColor: provider === "manual_smtp" ? "rgba(37, 99, 235, 0.10)" : "var(--surface-2)",
          }}
        >
          <span className="flex items-center gap-2">
            <SlidersHorizontal size={15} />
            {t("email.provider.manual")}
          </span>
        </button>
      </div>

      {provider === "resend_smtp" ? (
        <div className="mt-4 rounded-lg border p-3 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <p className="font-semibold">{t("email.resend.title")}</p>
          <ul className="mt-2 grid gap-1" style={{ color: "var(--muted)" }}>
            <li>{t("email.resend.verified")}</li>
            <li>{t("email.resend.sender")}</li>
            <li>{t("email.resend.tracking")}</li>
            <li>{t("email.resend.receiving")}</li>
            <li>{t("email.resend.tls")}</li>
          </ul>
          <div className="mt-3 flex items-start gap-2 rounded-md border p-2" style={{ borderColor: "#f59e0b", color: "#92400e" }}>
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{t("email.resend.warning")}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
