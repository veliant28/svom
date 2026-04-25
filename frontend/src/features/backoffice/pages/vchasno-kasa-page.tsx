"use client";

import { ExternalLink, LoaderCircle, Play, RefreshCw, Save } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import {
  closeBackofficeVchasnoKasaShift,
  getBackofficeOrderReceiptOpenUrl,
  getBackofficeVchasnoKasaSettings,
  getBackofficeVchasnoKasaShiftStatus,
  listBackofficeVchasnoReceipts,
  openBackofficeVchasnoKasaShift,
  syncBackofficeOrderReceipt,
  testBackofficeVchasnoKasaConnection,
  updateBackofficeVchasnoKasaSettings,
} from "@/features/backoffice/api/vchasno-kasa-api";
import { VchasnoCodesModal } from "@/features/backoffice/components/vchasno-kasa/vchasno-codes-modal";
import { VchasnoField, VchasnoStatusRow, VchasnoToggleField } from "@/features/backoffice/components/vchasno-kasa/vchasno-form-fields";
import { VchasnoPaymentMethodsField } from "@/features/backoffice/components/vchasno-kasa/vchasno-payment-methods-field";
import { VchasnoTaxGroupsField } from "@/features/backoffice/components/vchasno-kasa/vchasno-tax-groups-field";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { VCHASNO_PAYMENT_METHOD_ENTRIES, VCHASNO_TAX_GROUP_ENTRIES } from "@/features/backoffice/lib/vchasno-kasa-dictionaries";
import {
  DEFAULT_FORM,
  arraysEqual,
  formatDateTime,
  resolveConnectionCheckMessage,
  resolveLastCheckMessage,
  resolveShiftMessage,
  resolveShiftStatusLabel,
  resolveStatusLabel,
  toVchasnoKasaSettingsForm,
  type SettingsForm,
} from "@/features/backoffice/lib/vchasno-kasa-page.helpers";
import type {
  BackofficeVchasnoKasaSettings,
  BackofficeVchasnoKasaShiftStatus,
  BackofficeVchasnoReceiptRow,
} from "@/features/backoffice/types/vchasno-kasa.types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { isApiRequestError } from "@/shared/api/http-client";

type FieldErrors = Partial<Record<"api_token" | "rro_fn", string>>;

export function VchasnoKasaPage() {
  const t = useTranslations("backoffice.common");
  const locale = useLocale();
  const { token } = useAuth();
  const { showApiError, showSuccess, showWarning, showInfo } = useBackofficeFeedback();
  const [settings, setSettings] = useState<BackofficeVchasnoKasaSettings | null>(null);
  const [shiftStatus, setShiftStatus] = useState<BackofficeVchasnoKasaShiftStatus | null>(null);
  const [receipts, setReceipts] = useState<BackofficeVchasnoReceiptRow[]>([]);
  const [form, setForm] = useState<SettingsForm>(DEFAULT_FORM);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isRefreshingShift, setIsRefreshingShift] = useState(false);
  const [isOpeningShift, setIsOpeningShift] = useState(false);
  const [isClosingShift, setIsClosingShift] = useState(false);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [isPaymentCodesModalOpen, setIsPaymentCodesModalOpen] = useState(false);
  const [isTaxCodesModalOpen, setIsTaxCodesModalOpen] = useState(false);

  const paymentMethodOptions = useMemo(
    () => VCHASNO_PAYMENT_METHOD_ENTRIES.map((entry) => ({
      code: entry.code,
      label: t(`vchasnoKasa.paymentMethods.items.${entry.code}`),
    })),
    [t],
  );
  const taxGroupOptions = useMemo(
    () => VCHASNO_TAX_GROUP_ENTRIES.map((entry) => ({
      code: entry.code,
      label: t(`vchasnoKasa.taxGroups.items.${entry.code}`),
    })),
    [t],
  );
  const fiscalTokenHint = useMemo(() => {
    if (settings?.fiscal_api_token_masked) {
      return `${t("vchasnoKasa.form.fiscalApiTokenMasked")}: ${settings.fiscal_api_token_masked}`;
    }
    if (settings?.api_token_masked) {
      return `${t("vchasnoKasa.form.fiscalApiTokenFallbackMasked")}: ${settings.api_token_masked}`;
    }
    return "";
  }, [settings?.api_token_masked, settings?.fiscal_api_token_masked, t]);

  const load = useCallback(async () => {
    if (!token) {
      setIsLoading(false);
      setLoadError(null);
      return false;
    }
    setIsLoading(true);
    setLoadError(null);
    try {
      const [nextSettings, receiptList] = await Promise.all([
        getBackofficeVchasnoKasaSettings(token),
        listBackofficeVchasnoReceipts(token),
      ]);
      setSettings(nextSettings);
      setForm(toVchasnoKasaSettingsForm(nextSettings));
      setReceipts(receiptList.results || []);
      try {
        const nextShiftStatus = await getBackofficeVchasnoKasaShiftStatus(token);
        setShiftStatus(nextShiftStatus);
      } catch {
        setShiftStatus(null);
      }
      setFieldErrors({});
      return true;
    } catch (error) {
      setLoadError(showApiError(error, t("vchasnoKasa.messages.loadFailed")));
      return false;
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
      || !arraysEqual(settings.selected_payment_methods || [], form.selected_payment_methods)
      || !arraysEqual(settings.selected_tax_groups || [], form.selected_tax_groups)
      || settings.auto_issue_on_completed !== form.auto_issue_on_completed
      || settings.send_customer_email !== form.send_customer_email
      || Boolean(form.api_token.trim())
      || Boolean(form.fiscal_api_token.trim())
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
        fiscal_api_token: form.fiscal_api_token.trim(),
        rro_fn: form.rro_fn.trim(),
        default_payment_type: form.default_payment_type,
        default_tax_group: form.default_tax_group.trim(),
        selected_payment_methods: form.selected_payment_methods,
        selected_tax_groups: form.selected_tax_groups,
        auto_issue_on_completed: form.auto_issue_on_completed,
        send_customer_email: form.send_customer_email,
      });
      setSettings(next);
      setForm(toVchasnoKasaSettingsForm(next));
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

  async function handleRefreshShiftStatus() {
    if (!token || isRefreshingShift) {
      return;
    }
    setIsRefreshingShift(true);
    try {
      const next = await getBackofficeVchasnoKasaShiftStatus(token);
      setShiftStatus(next);
      const statusLabel = resolveShiftStatusLabel(next.status_key || "unknown", t);
      const localizedMessage = resolveShiftMessage(next.message || "", t);
      if (next.status_key === "error") {
        showWarning(localizedMessage || t("vchasnoKasa.messages.shiftStatusFailed"));
      } else {
        showInfo(t("vchasnoKasa.messages.shiftStatusUpdated", { status: statusLabel }));
      }
    } catch (error) {
      showApiError(error, t("vchasnoKasa.messages.shiftStatusFailed"));
    } finally {
      setIsRefreshingShift(false);
    }
  }

  async function handleOpenShift() {
    if (!token || isOpeningShift) {
      return;
    }
    setIsOpeningShift(true);
    try {
      const next = await openBackofficeVchasnoKasaShift(token);
      setShiftStatus(next);
      showSuccess(resolveShiftMessage(next.message || "", t) || t("vchasnoKasa.messages.shiftOpened"));
    } catch (error) {
      showApiError(error, t("vchasnoKasa.messages.shiftOpenFailed"));
    } finally {
      setIsOpeningShift(false);
    }
  }

  async function handleCloseShift() {
    if (!token || isClosingShift) {
      return;
    }
    setIsClosingShift(true);
    try {
      const next = await closeBackofficeVchasnoKasaShift(token);
      setShiftStatus(next);
      showSuccess(resolveShiftMessage(next.message || "", t) || t("vchasnoKasa.messages.shiftClosed"));
    } catch (error) {
      showApiError(error, t("vchasnoKasa.messages.shiftCloseFailed"));
    } finally {
      setIsClosingShift(false);
    }
  }

  async function handleTestConnection() {
    if (!token || isTesting) {
      return;
    }
    setIsTesting(true);
    try {
      const result = await testBackofficeVchasnoKasaConnection(token);
      const localizedMessage = resolveConnectionCheckMessage(result.message || "", t);
      if (result.ok) {
        showSuccess(t("vchasnoKasa.messages.connectionOk"));
      } else {
        showWarning(localizedMessage || t("vchasnoKasa.messages.connectionFailed"));
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
      } else {
        showInfo(t("vchasnoKasa.messages.receiptOpened"));
      }
    } catch (error) {
      showApiError(error, t("vchasnoKasa.messages.receiptOpenFailed"));
    } finally {
      setActiveAction(null);
    }
  }

  async function handleRefreshData() {
    if (!token || isLoading) {
      return;
    }
    const ok = await load();
    if (ok) {
      showInfo(t("vchasnoKasa.messages.dataRefreshed"));
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
              <VchasnoToggleField
                label={t("vchasnoKasa.form.enabled")}
                value={form.is_enabled}
                onToggle={() => setForm((prev) => ({ ...prev, is_enabled: !prev.is_enabled }))}
              />
              <VchasnoField
                label={t("vchasnoKasa.form.apiToken")}
                hint={settings?.api_token_masked ? `${t("vchasnoKasa.form.apiTokenMasked")}: ${settings.api_token_masked}` : ""}
                error={fieldErrors.api_token}
              >
                <input
                  value={form.api_token}
                  onChange={(event) => setForm((prev) => ({ ...prev, api_token: event.target.value }))}
                  className="h-10 rounded-md border px-3 text-sm"
                  style={{ borderColor: fieldErrors.api_token ? "#fda4af" : "var(--border)", backgroundColor: "var(--surface-2)" }}
                />
              </VchasnoField>
              <VchasnoField
                label={t("vchasnoKasa.form.fiscalApiToken")}
                hint={fiscalTokenHint}
              >
                <input
                  value={form.fiscal_api_token}
                  onChange={(event) => setForm((prev) => ({ ...prev, fiscal_api_token: event.target.value }))}
                  className="h-10 rounded-md border px-3 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                />
              </VchasnoField>
              <VchasnoField label={t("vchasnoKasa.form.rroFn")} error={fieldErrors.rro_fn}>
                <input
                  value={form.rro_fn}
                  onChange={(event) => setForm((prev) => ({ ...prev, rro_fn: event.target.value }))}
                  className="h-10 rounded-md border px-3 text-sm"
                  style={{ borderColor: fieldErrors.rro_fn ? "#fda4af" : "var(--border)", backgroundColor: "var(--surface-2)" }}
                />
              </VchasnoField>

              <VchasnoPaymentMethodsField
                title={t("vchasnoKasa.paymentMethods.title")}
                codesActionLabel={t("vchasnoKasa.paymentMethods.codes")}
                options={paymentMethodOptions}
                values={form.selected_payment_methods}
                onChange={(next) => setForm((prev) => ({ ...prev, selected_payment_methods: next }))}
                onOpenCodes={() => setIsPaymentCodesModalOpen(true)}
              />
              <VchasnoTaxGroupsField
                title={t("vchasnoKasa.taxGroups.title")}
                codesActionLabel={t("vchasnoKasa.taxGroups.codes")}
                options={taxGroupOptions}
                values={form.selected_tax_groups}
                onChange={(next) => setForm((prev) => ({ ...prev, selected_tax_groups: next }))}
                onOpenCodes={() => setIsTaxCodesModalOpen(true)}
              />

              <VchasnoToggleField
                label={t("vchasnoKasa.form.autoIssueOnCompleted")}
                value={form.auto_issue_on_completed}
                onToggle={() => setForm((prev) => ({ ...prev, auto_issue_on_completed: !prev.auto_issue_on_completed }))}
              />
              <VchasnoToggleField
                label={t("vchasnoKasa.form.sendCustomerEmail")}
                value={form.send_customer_email}
                onToggle={() => setForm((prev) => ({ ...prev, send_customer_email: !prev.send_customer_email }))}
              />

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
                  <RefreshCw className="h-4 w-4 animate-spin" style={{ animationDuration: "2.2s" }} />
                  {isTesting ? t("vchasnoKasa.form.testing") : t("vchasnoKasa.form.testConnection")}
                </button>
              </div>
            </div>
          </section>

          <div className="grid gap-4">
            <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <p className="text-sm font-semibold">{t("vchasnoKasa.status.title")}</p>
              <div className="mt-4 grid gap-2">
                <VchasnoStatusRow label={t("vchasnoKasa.status.enabled")} value={settings?.is_enabled ? t("yes") : t("no")} />
                <VchasnoStatusRow
                  label={t("vchasnoKasa.status.lastCheckState")}
                  value={settings?.last_connection_ok === null ? "-" : settings?.last_connection_ok ? t("vchasnoKasa.status.ok") : t("vchasnoKasa.status.failed")}
                />
                <VchasnoStatusRow
                  label={t("vchasnoKasa.status.lastCheck")}
                  value={formatDateTime(settings?.last_connection_checked_at, locale)}
                />
                <VchasnoStatusRow label={t("vchasnoKasa.status.rroFn")} value={settings?.rro_fn || "-"} mono />
                <VchasnoStatusRow label={t("vchasnoKasa.status.ordersApiToken")} value={settings?.api_token_masked || "-"} mono />
                <VchasnoStatusRow
                  label={t("vchasnoKasa.status.fiscalApiToken")}
                  value={settings?.fiscal_api_token_masked || settings?.api_token_masked || "-"}
                  mono
                />
                <VchasnoStatusRow
                  label={t("vchasnoKasa.status.lastCheckMessage")}
                  value={resolveLastCheckMessage(settings?.last_connection_message || "", t)}
                />
              </div>
            </section>

            <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <p className="text-sm font-semibold">{t("vchasnoKasa.shift.title")}</p>
              <div className="mt-4 grid gap-2">
                <VchasnoStatusRow label={t("vchasnoKasa.shift.state")} value={resolveShiftStatusLabel(shiftStatus?.status_key || "unknown", t)} />
                <VchasnoStatusRow label={t("vchasnoKasa.shift.shiftId")} value={shiftStatus?.shift_id || "-"} mono />
                <VchasnoStatusRow label={t("vchasnoKasa.shift.shiftLink")} value={shiftStatus?.shift_link || "-"} />
                <VchasnoStatusRow label={t("vchasnoKasa.shift.checkedAt")} value={formatDateTime(shiftStatus?.checked_at, locale)} />
              </div>
              <p className="mt-3 text-xs" style={{ color: "var(--muted)" }}>
                {t("vchasnoKasa.shift.message")}: {resolveShiftMessage(shiftStatus?.message || "", t) || "-"}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  disabled={isRefreshingShift}
                  onClick={() => {
                    void handleRefreshShiftStatus();
                  }}
                >
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" style={{ animationDuration: "2.2s" }} />
                  {t("vchasnoKasa.shift.refresh")}
                </button>
                <button
                  type="button"
                  className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
                  style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
                  disabled={isOpeningShift || isClosingShift || shiftStatus?.is_open === true}
                  onClick={() => {
                    void handleOpenShift();
                  }}
                >
                  {isOpeningShift ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                  {t("vchasnoKasa.shift.open")}
                </button>
                <button
                  type="button"
                  className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
                  style={{ borderColor: "#dc2626", backgroundColor: "#dc2626", color: "#fff" }}
                  disabled={isClosingShift || isOpeningShift || shiftStatus?.is_open !== true}
                  onClick={() => {
                    void handleCloseShift();
                  }}
                >
                  {isClosingShift ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <span className="inline-block h-3 w-3 rounded-[2px] bg-current" />}
                  {t("vchasnoKasa.shift.close")}
                </button>
              </div>
            </section>
          </div>
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
              disabled={isLoading}
              onClick={() => {
                void handleRefreshData();
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
                    <td className="border-t px-3 py-2" style={{ borderColor: "var(--border)" }}>{formatDateTime(row.updated_at || row.created_at, locale)}</td>
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

      <VchasnoCodesModal
        isOpen={isPaymentCodesModalOpen}
        title={t("vchasnoKasa.codes.paymentMethodsTitle")}
        rows={paymentMethodOptions}
        rightColumnLabel={t("vchasnoKasa.codes.paymentMethod")}
        codeLabel={t("vchasnoKasa.codes.code")}
        closeLabel={t("vchasnoKasa.codes.close")}
        onClose={() => setIsPaymentCodesModalOpen(false)}
      />
      <VchasnoCodesModal
        isOpen={isTaxCodesModalOpen}
        title={t("vchasnoKasa.codes.taxGroupsTitle")}
        rows={taxGroupOptions}
        rightColumnLabel={t("vchasnoKasa.codes.taxGroup")}
        codeLabel={t("vchasnoKasa.codes.code")}
        closeLabel={t("vchasnoKasa.codes.close")}
        onClose={() => setIsTaxCodesModalOpen(false)}
      />
    </AsyncState>
  );
}
