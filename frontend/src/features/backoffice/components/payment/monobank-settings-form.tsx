"use client";

import { useEffect, useMemo, useState } from "react";

import type { BackofficeMonobankSettings } from "@/features/backoffice/types/payment.types";

export function MonobankSettingsForm({
  settings,
  isSaving,
  isTesting,
  onSave,
  onTestConnection,
  t,
}: {
  settings: BackofficeMonobankSettings | null;
  isSaving: boolean;
  isTesting: boolean;
  onSave: (payload: Partial<{ is_enabled: boolean; merchant_token: string; widget_key_id: string; widget_private_key: string }>) => Promise<unknown>;
  onTestConnection: () => Promise<unknown>;
  t: (key: string) => string;
}) {
  const [enabled, setEnabled] = useState<boolean>(Boolean(settings?.is_enabled));
  const [token, setToken] = useState("");
  const [widgetKeyId, setWidgetKeyId] = useState(settings?.widget_key_id || "");
  const [widgetPrivateKey, setWidgetPrivateKey] = useState("");

  const tokenMasked = settings?.merchant_token_masked || "";
  const widgetPrivateKeyMasked = settings?.widget_private_key_masked || "";

  const canSave = useMemo(() => !isSaving, [isSaving]);

  useEffect(() => {
    setEnabled(Boolean(settings?.is_enabled));
    setWidgetKeyId(settings?.widget_key_id || "");
  }, [settings?.is_enabled, settings?.widget_key_id]);

  return (
    <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{t("payments.monobank.title")}</p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("payments.monobank.helper")}</p>

      <div className="mt-3 grid gap-3">
        <label className="inline-flex items-center gap-2 text-xs font-medium">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          {t("payments.monobank.enabled")}
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {t("payments.monobank.token")}
          <input
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder={tokenMasked || "****"}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          {tokenMasked ? <span style={{ color: "var(--muted)" }}>{t("payments.monobank.tokenMasked")}: {tokenMasked}</span> : null}
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {t("payments.monobank.widgetKeyId")}
          <input
            value={widgetKeyId}
            onChange={(event) => setWidgetKeyId(event.target.value)}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {t("payments.monobank.widgetPrivateKey")}
          <textarea
            value={widgetPrivateKey}
            onChange={(event) => setWidgetPrivateKey(event.target.value)}
            placeholder={widgetPrivateKeyMasked || "************"}
            rows={4}
            className="rounded-md border px-3 py-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          {widgetPrivateKeyMasked ? <span style={{ color: "var(--muted)" }}>{t("payments.monobank.widgetPrivateKeyMasked")}: {widgetPrivateKeyMasked}</span> : null}
        </label>

        <div className="grid gap-2 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs">
            {t("payments.monobank.webhookUrl")}
            <input value={settings?.webhook_url || ""} readOnly className="h-10 rounded-md border px-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }} />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            {t("payments.monobank.redirectUrl")}
            <input value={settings?.redirect_url || ""} readOnly className="h-10 rounded-md border px-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }} />
          </label>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-md border px-3 py-2 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            disabled={!canSave}
            onClick={() => {
              const payload: Partial<{ is_enabled: boolean; merchant_token: string; widget_key_id: string; widget_private_key: string }> = {
                is_enabled: enabled,
                widget_key_id: widgetKeyId,
              };
              if (token.trim()) {
                payload.merchant_token = token.trim();
              }
              if (widgetPrivateKey.trim()) {
                payload.widget_private_key = widgetPrivateKey.trim();
              }
              void onSave(payload).then(() => {
                setToken("");
                setWidgetPrivateKey("");
              });
            }}
          >
            {isSaving ? t("payments.monobank.saving") : t("payments.monobank.save")}
          </button>

          <button
            type="button"
            className="rounded-md border px-3 py-2 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            disabled={isTesting}
            onClick={() => {
              void onTestConnection();
            }}
          >
            {isTesting ? t("payments.monobank.testing") : t("payments.monobank.testConnection")}
          </button>
        </div>
      </div>
    </div>
  );
}
