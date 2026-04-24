"use client";

import { ExternalLink, LoaderCircle, RefreshCw, Save } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getBackofficeOrderReceiptOpenUrl,
  getBackofficeVchasnoKasaSettings,
  listBackofficeVchasnoReceipts,
  syncBackofficeOrderReceipt,
  testBackofficeVchasnoKasaConnection,
  updateBackofficeVchasnoKasaSettings,
} from "@/features/backoffice/api/vchasno-kasa-api";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import type { BackofficeVchasnoKasaSettings, BackofficeVchasnoReceiptRow } from "@/features/backoffice/types/vchasno-kasa.types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { isApiRequestError } from "@/shared/api/http-client";

type SettingsForm = {
  is_enabled: boolean;
  api_token: string;
  rro_fn: string;
  default_payment_type: number;
  default_tax_group: string;
  auto_issue_on_completed: boolean;
  send_customer_email: boolean;
};

type FieldErrors = Partial<Record<"api_token" | "rro_fn", string>>;

const DEFAULT_FORM: SettingsForm = {
  is_enabled: false,
  api_token: "",
  rro_fn: "",
  default_payment_type: 1,
  default_tax_group: "",
  auto_issue_on_completed: true,
  send_customer_email: true,
};

function toForm(settings: BackofficeVchasnoKasaSettings | null): SettingsForm {
  if (!settings) {
    return DEFAULT_FORM;
  }
  return {
    is_enabled: settings.is_enabled,
    api_token: "",
    rro_fn: settings.rro_fn || "",
    default_payment_type: settings.default_payment_type || 1,
    default_tax_group: settings.default_tax_group || "",
    auto_issue_on_completed: settings.auto_issue_on_completed,
    send_customer_email: settings.send_customer_email,
  };
}

export function VchasnoKasaPage() {
  const t = useTranslations("backoffice.common");
  const { token } = useAuth();
  const { showApiError, showSuccess, showWarning } = useBackofficeFeedback();
  const [settings, setSettings] = useState<BackofficeVchasnoKasaSettings | null>(null);
  const [receipts, setReceipts] = useState<BackofficeVchasnoReceiptRow[]>([]);
  const [form, setForm] = useState<SettingsForm>(DEFAULT_FORM);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [activeAction, setActiveAction] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      setIsLoading(false);
      setLoadError(null);
      return;
    }
    setIsLoading(true);
    setLoadError(null);
    try {
      const [nextSettings, receiptList] = await Promise.all([
        getBackofficeVchasnoKasaSettings(token),
        listBackofficeVchasnoReceipts(token),
      ]);
      setSettings(nextSettings);
      setForm(toForm(nextSettings));
      setReceipts(receiptList.results || []);
      setFieldErrors({});
    } catch (error) {
      setLoadError(showApiError(error, t("vchasnoKasa.messages.loadFailed")));
    } finally {
      setIsLoading(false);
    }
  }, [showApiError, t, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const isDirty = useMemo(() => {
    if (!settings) {
      return false;
    }
    return (
      settings.is_enabled !== form.is_enabled
      || settings.rro_fn !== form.rro_fn
      || settings.default_payment_type !== form.default_payment_type
      || settings.default_tax_group !== form.default_tax_group
      || settings.auto_issue_on_completed !== form.auto_issue_on_completed
      || settings.send_customer_email !== form.send_customer_email
      || Boolean(form.api_token.trim())
    );
  }, [form, settings]);

  async function handleSave() {
    if (!token || isSaving) {
      return;
    }
    setIsSaving(true);
    setFieldErrors({});
    try {
      const next = await updateBackofficeVchasnoKasaSettings(token, {
        is_enabled: form.is_enabled,
        api_token: form.api_token.trim(),
        rro_fn: form.rro_fn.trim(),
        default_payment_type: form.default_payment_type,
        default_tax_group: form.default_tax_group.trim(),
        auto_issue_on_completed: form.auto_issue_on_completed,
        send_customer_email: form.send_customer_email,
      });
      setSettings(next);
      setForm(toForm(next));
      showSuccess(t("vchasnoKasa.messages.settingsSaved"));
    } catch (error) {
      const nextFieldErrors: FieldErrors = {};
      if (isApiRequestError(error) && error.payload) {
        if (Array.isArray(error.payload.api_token)) {
          nextFieldErrors.api_token = t("vchasnoKasa.validation.tokenRequired");
        }
        if (Array.isArray(error.payload.rro_fn)) {
          nextFieldErrors.rro_fn = t("vchasnoKasa.validation.rroRequired");
        }
      }
      setFieldErrors(nextFieldErrors);
      showApiError(error, t("vchasnoKasa.messages.settingsSaveFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleTestConnection() {
    if (!token || isTesting) {
      return;
    }
    setIsTesting(true);
    try {
      const result = await testBackofficeVchasnoKasaConnection(token);
      if (result.ok) {
        showSuccess(t("vchasnoKasa.messages.connectionOk"));
      } else {
        showWarning(result.message || t("vchasnoKasa.messages.connectionFailed"));
      }
      await load();
    } catch (error) {
      showApiError(error, t("vchasnoKasa.messages.connectionFailed"));
    } finally {
      setIsTesting(false);
    }
  }

  async function handleSyncReceipt(orderId: string) {
    if (!token || activeAction) {
      return;
    }
    setActiveAction(`sync:${orderId}`);
    try {
      await syncBackofficeOrderReceipt(token, orderId);
      showSuccess(t("vchasnoKasa.messages.receiptSynced"));
      await load();
    } catch (error) {
      showApiError(error, t("vchasnoKasa.messages.receiptSyncFailed"));
    } finally {
      setActiveAction(null);
    }
  }

  async function handleOpenReceipt(orderId: string) {
    if (!token || activeAction) {
      return;
    }
    setActiveAction(`open:${orderId}`);
    try {
      const { url } = await getBackofficeOrderReceiptOpenUrl(token, orderId);
      const opened = window.open(url, "_blank", "noopener,noreferrer");
      if (!opened) {
        showWarning(t("vchasnoKasa.messages.popupBlocked"));
      }
    } catch (error) {
      showApiError(error, t("vchasnoKasa.messages.receiptOpenFailed"));
    } finally {
      setActiveAction(null);
    }
  }

  return (
    <AsyncState isLoading={isLoading} error={loadError} empty={false} emptyLabel="">
      <section className="grid gap-4">
        <PageHeader title={t("vchasnoKasa.title")} description={t("vchasnoKasa.subtitle")} />

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <p className="text-sm font-semibold">{t("vchasnoKasa.form.title")}</p>
            <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("vchasnoKasa.form.helper")}</p>

            <div className="mt-4 grid gap-3">
              <ToggleField label={t("vchasnoKasa.form.enabled")} value={form.is_enabled} onToggle={() => setForm((prev) => ({ ...prev, is_enabled: !prev.is_enabled }))} />
              <Field label={t("vchasnoKasa.form.apiToken")} hint={settings?.api_token_masked ? `${t("vchasnoKasa.form.apiTokenMasked")}: ${settings.api_token_masked}` : ""} error={fieldErrors.api_token}>
                <input
                  value={form.api_token}
                  onChange={(event) => setForm((prev) => ({ ...prev, api_token: event.target.value }))}
                  className="h-10 rounded-md border px-3 text-sm"
                  style={{ borderColor: fieldErrors.api_token ? "#fda4af" : "var(--border)", backgroundColor: "var(--surface-2)" }}
                />
              </Field>
              <Field label={t("vchasnoKasa.form.rroFn")} error={fieldErrors.rro_fn}>
                <input
                  value={form.rro_fn}
                  onChange={(event) => setForm((prev) => ({ ...prev, rro_fn: event.target.value }))}
                  className="h-10 rounded-md border px-3 text-sm"
                  style={{ borderColor: fieldErrors.rro_fn ? "#fda4af" : "var(--border)", backgroundColor: "var(--surface-2)" }}
                />
              </Field>

              <div className="grid gap-3 md:grid-cols-2">
                <Field label={t("vchasnoKasa.form.defaultPaymentType")}>
                  <input
                    type="number"
                    min={1}
                    value={form.default_payment_type}
                    onChange={(event) => setForm((prev) => ({ ...prev, default_payment_type: Math.max(1, Number(event.target.value) || 1) }))}
                    className="h-10 rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  />
                </Field>
                <Field label={t("vchasnoKasa.form.defaultTaxGroup")}>
                  <input
                    value={form.default_tax_group}
                    onChange={(event) => setForm((prev) => ({ ...prev, default_tax_group: event.target.value }))}
                    className="h-10 rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  />
                </Field>
              </div>

              <ToggleField label={t("vchasnoKasa.form.autoIssueOnCompleted")} value={form.auto_issue_on_completed} onToggle={() => setForm((prev) => ({ ...prev, auto_issue_on_completed: !prev.auto_issue_on_completed }))} />
              <ToggleField label={t("vchasnoKasa.form.sendCustomerEmail")} value={form.send_customer_email} onToggle={() => setForm((prev) => ({ ...prev, send_customer_email: !prev.send_customer_email }))} />

              <div className="flex flex-wrap gap-2 pt-1">
                <button
                  type="button"
                  className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold disabled:opacity-60"
                  style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
                  disabled={!isDirty || isSaving}
                  onClick={() => {
                    void handleSave();
                  }}
                >
                  {isSaving ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  {isSaving ? t("vchasnoKasa.form.saving") : t("vchasnoKasa.form.save")}
                </button>
                <button
                  type="button"
                  className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold disabled:opacity-60"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  disabled={isTesting}
                  onClick={() => {
                    void handleTestConnection();
                  }}
                >
                  {isTesting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  {isTesting ? t("vchasnoKasa.form.testing") : t("vchasnoKasa.form.testConnection")}
                </button>
              </div>
            </div>
          </section>

          <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <p className="text-sm font-semibold">{t("vchasnoKasa.status.title")}</p>
            <div className="mt-4 grid gap-2">
              <StatusRow label={t("vchasnoKasa.status.enabled")} value={settings?.is_enabled ? t("yes") : t("no")} />
              <StatusRow label={t("vchasnoKasa.status.rroFn")} value={settings?.rro_fn || "-"} mono />
              <StatusRow label={t("vchasnoKasa.status.lastCheck")} value={settings?.last_connection_checked_at || "-"} />
              <StatusRow label={t("vchasnoKasa.status.lastCheckState")} value={settings?.last_connection_ok === null ? "-" : settings?.last_connection_ok ? t("vchasnoKasa.status.ok") : t("vchasnoKasa.status.failed")} />
              <StatusRow label={t("vchasnoKasa.status.lastCheckMessage")} value={settings?.last_connection_message || "-"} />
            </div>
          </section>
        </div>

        <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold">{t("vchasnoKasa.latest.title")}</p>
              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("vchasnoKasa.latest.subtitle")}</p>
            </div>
            <button
              type="button"
              className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              onClick={() => {
                void load();
              }}
            >
              <RefreshCw className="h-4 w-4 animate-spin" style={{ animationDuration: "2.2s" }} />
              {t("vchasnoKasa.latest.refresh")}
            </button>
          </div>

          <div className="overflow-x-auto rounded-lg border" style={{ borderColor: "var(--border)" }}>
            <table className="min-w-full border-separate border-spacing-0 text-sm">
              <thead style={{ backgroundColor: "var(--surface-2)", color: "var(--muted)" }}>
                <tr>
                  <th className="px-3 py-2 text-left font-medium">{t("vchasnoKasa.latest.order")}</th>
                  <th className="px-3 py-2 text-left font-medium">{t("vchasnoKasa.latest.customer")}</th>
                  <th className="px-3 py-2 text-left font-medium">{t("vchasnoKasa.latest.amount")}</th>
                  <th className="px-3 py-2 text-left font-medium">{t("vchasnoKasa.latest.status")}</th>
                  <th className="px-3 py-2 text-left font-medium">{t("vchasnoKasa.latest.checkFn")}</th>
                  <th className="px-3 py-2 text-left font-medium">{t("vchasnoKasa.latest.date")}</th>
                  <th className="px-3 py-2 text-right font-medium">{t("vchasnoKasa.latest.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {receipts.length ? receipts.map((row) => (
                  <tr key={row.id}>
                    <td className="border-t px-3 py-2" style={{ borderColor: "var(--border)" }}>{row.order_number}</td>
                    <td className="border-t px-3 py-2" style={{ borderColor: "var(--border)" }}>{row.customer_name || "-"}</td>
                    <td className="border-t px-3 py-2" style={{ borderColor: "var(--border)" }}>{row.amount} {row.currency}</td>
                    <td className="border-t px-3 py-2" style={{ borderColor: "var(--border)" }}>{resolveStatusLabel(row.status_key, t)}</td>
                    <td className="border-t px-3 py-2 font-mono" style={{ borderColor: "var(--border)" }}>{row.check_fn || "-"}</td>
                    <td className="border-t px-3 py-2" style={{ borderColor: "var(--border)" }}>{row.updated_at || row.created_at}</td>
                    <td className="border-t px-3 py-2 text-right" style={{ borderColor: "var(--border)" }}>
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          className="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs font-semibold disabled:opacity-60"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          disabled={activeAction !== null}
                          onClick={() => {
                            void handleSyncReceipt(row.order_id);
                          }}
                        >
                          {activeAction === `sync:${row.order_id}` ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                          {t("vchasnoKasa.latest.sync")}
                        </button>
                        <button
                          type="button"
                          className="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs font-semibold disabled:opacity-60"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          disabled={activeAction !== null || !row.receipt_url}
                          onClick={() => {
                            void handleOpenReceipt(row.order_id);
                          }}
                        >
                          {activeAction === `open:${row.order_id}` ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <ExternalLink className="h-3.5 w-3.5" />}
                          {t("vchasnoKasa.latest.open")}
                        </button>
                      </div>
                    </td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={7} className="px-3 py-6 text-center text-sm" style={{ color: "var(--muted)" }}>
                      {t("vchasnoKasa.latest.empty")}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </section>
    </AsyncState>
  );
}

function resolveStatusLabel(statusKey: string, t: (key: string) => string): string {
  const translationKey = `vchasnoKasa.receiptStatus.${statusKey || "pending"}`;
  const translated = t(translationKey);
  return translated === translationKey ? t("vchasnoKasa.receiptStatus.pending") : translated;
}

function Field({
  label,
  children,
  hint,
  error,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
  error?: string;
}) {
  return (
    <label className="grid gap-1">
      <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>{label}</span>
      {children}
      {hint ? <span className="text-xs" style={{ color: "var(--muted)" }}>{hint}</span> : null}
      {error ? <span className="text-xs" style={{ color: "#b91c1c" }}>{error}</span> : null}
    </label>
  );
}

function ToggleField({ label, value, onToggle }: { label: string; value: boolean; onToggle: () => void }) {
  return (
    <label className="inline-flex items-center gap-2 text-sm font-medium">
      <input type="checkbox" checked={value} onChange={onToggle} />
      <span>{label}</span>
    </label>
  );
}

function StatusRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <p className="text-[11px]" style={{ color: "var(--muted)" }}>{label}</p>
      <p className={`mt-1 text-sm font-medium text-[var(--text)] ${mono ? "font-mono" : ""}`}>{value || "-"}</p>
    </div>
  );
}
