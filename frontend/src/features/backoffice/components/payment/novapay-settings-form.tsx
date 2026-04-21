"use client";

import { useEffect, useMemo, useState } from "react";

import type { BackofficeNovaPaySettings } from "@/features/backoffice/types/payment.types";

export function NovaPaySettingsForm({
  settings,
  isSaving,
  isTesting,
  isLoading,
  onSave,
  onTestConnection,
  t,
}: {
  settings: BackofficeNovaPaySettings | null;
  isSaving: boolean;
  isTesting: boolean;
  isLoading: boolean;
  onSave: (payload: Partial<{ is_enabled: boolean; merchant_id: string; api_token: string }>) => Promise<unknown>;
  onTestConnection: () => Promise<unknown>;
  t: (key: string) => string;
}) {
  const [enabled, setEnabled] = useState<boolean>(Boolean(settings?.is_enabled));
  const [merchantId, setMerchantId] = useState(settings?.merchant_id || "");
  const [apiToken, setApiToken] = useState("");
  const apiTokenMasked = settings?.api_token_masked || "";

  const canSave = useMemo(() => !isSaving && !isLoading, [isLoading, isSaving]);

  useEffect(() => {
    setEnabled(Boolean(settings?.is_enabled));
    setMerchantId(settings?.merchant_id || "");
  }, [settings?.is_enabled, settings?.merchant_id]);

  return (
    <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{t("payments.novapay.title")}</p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("payments.novapay.helper")}</p>

      <div className="mt-3 grid gap-3">
        <label className="inline-flex items-center gap-2 text-xs font-medium">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          {t("payments.novapay.enabled")}
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {t("payments.novapay.merchantId")}
          <input
            value={merchantId}
            onChange={(event) => setMerchantId(event.target.value)}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {t("payments.novapay.apiToken")}
          <input
            value={apiToken}
            onChange={(event) => setApiToken(event.target.value)}
            placeholder={apiTokenMasked || "****"}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          {apiTokenMasked ? <span style={{ color: "var(--muted)" }}>{t("payments.novapay.apiTokenMasked")}: {apiTokenMasked}</span> : null}
        </label>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-md border px-3 py-2 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            disabled={!canSave}
            onClick={() => {
              const payload: Partial<{ is_enabled: boolean; merchant_id: string; api_token: string }> = {
                is_enabled: enabled,
                merchant_id: merchantId.trim(),
              };
              if (apiToken.trim()) {
                payload.api_token = apiToken.trim();
              }
              void onSave(payload).then(() => {
                setApiToken("");
              });
            }}
          >
            {isSaving ? t("payments.novapay.saving") : t("payments.novapay.save")}
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
            {isTesting ? t("payments.novapay.testing") : t("payments.novapay.testConnection")}
          </button>
        </div>
      </div>
    </div>
  );
}
