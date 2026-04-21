"use client";

import { useEffect, useMemo, useState } from "react";

import type { BackofficeLiqPaySettings } from "@/features/backoffice/types/payment.types";

export function LiqPaySettingsForm({
  settings,
  isSaving,
  isLoading,
  onSave,
  t,
}: {
  settings: BackofficeLiqPaySettings | null;
  isSaving: boolean;
  isLoading: boolean;
  onSave: (payload: Partial<{ is_enabled: boolean; public_key: string; private_key: string }>) => Promise<unknown>;
  t: (key: string) => string;
}) {
  const [enabled, setEnabled] = useState<boolean>(Boolean(settings?.is_enabled));
  const [publicKey, setPublicKey] = useState("");
  const [privateKey, setPrivateKey] = useState("");

  const canSave = useMemo(() => !isSaving && !isLoading, [isLoading, isSaving]);
  const fallbackOrigin = typeof window !== "undefined" ? window.location.origin : "";
  const serverUrlValue = settings?.server_url || (fallbackOrigin ? `${fallbackOrigin}/api/commerce/payments/liqpay/webhook/` : "");
  const resultUrlValue = settings?.result_url || (fallbackOrigin ? `${fallbackOrigin}/checkout` : "");

  useEffect(() => {
    setEnabled(Boolean(settings?.is_enabled));
  }, [settings?.is_enabled]);

  return (
    <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{t("payments.liqpay.title")}</p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("payments.liqpay.helper")}</p>

      <div className="mt-3 grid gap-3">
        <label className="inline-flex items-center gap-2 text-xs font-medium">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          {t("payments.liqpay.enabled")}
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {t("payments.liqpay.publicKey")}
          <input
            value={publicKey}
            onChange={(event) => setPublicKey(event.target.value)}
            placeholder={settings?.public_key_masked || "****"}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          {settings?.public_key_masked ? (
            <span style={{ color: "var(--muted)" }}>
              {t("payments.liqpay.publicKeyMasked")}: {settings.public_key_masked}
            </span>
          ) : null}
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {t("payments.liqpay.privateKey")}
          <input
            value={privateKey}
            onChange={(event) => setPrivateKey(event.target.value)}
            placeholder={settings?.private_key_masked || "****"}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          {settings?.private_key_masked ? (
            <span style={{ color: "var(--muted)" }}>
              {t("payments.liqpay.privateKeyMasked")}: {settings.private_key_masked}
            </span>
          ) : null}
        </label>

        <div className="grid gap-2 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs">
            {t("payments.liqpay.serverUrl")}
            <input
              value={serverUrlValue}
              readOnly
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            {t("payments.liqpay.resultUrl")}
            <input
              value={resultUrlValue}
              readOnly
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }}
            />
          </label>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-md border px-3 py-2 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            disabled={!canSave}
            onClick={() => {
              const payload: Partial<{ is_enabled: boolean; public_key: string; private_key: string }> = {
                is_enabled: enabled,
              };
              if (publicKey.trim()) {
                payload.public_key = publicKey.trim();
              }
              if (privateKey.trim()) {
                payload.private_key = privateKey.trim();
              }
              void onSave(payload).then(() => {
                setPublicKey("");
                setPrivateKey("");
              });
            }}
          >
            {isSaving ? t("payments.liqpay.saving") : t("payments.liqpay.save")}
          </button>
        </div>
      </div>
    </div>
  );
}
