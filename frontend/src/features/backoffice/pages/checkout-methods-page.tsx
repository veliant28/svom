"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CreditCard, Store, Truck } from "lucide-react";
import { useTranslations } from "next-intl";

import {
  getCheckoutMethodSettings,
  updateCheckoutMethodSettings,
} from "@/features/backoffice/api/checkout-method-settings-api";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { CheckoutMethodSettings } from "@/features/backoffice/types/checkout-method-settings.types";

type MethodField = keyof CheckoutMethodSettings;
type Translator = (key: string) => string;

const DELIVERY_FIELDS: MethodField[] = ["pickup_enabled", "nova_poshta_enabled", "courier_enabled"];
const PAYMENT_FIELDS: MethodField[] = ["cash_on_delivery_enabled", "monobank_enabled", "novapay_enabled", "liqpay_enabled"];

const EMPTY_SETTINGS: CheckoutMethodSettings = {
  pickup_enabled: true,
  nova_poshta_enabled: true,
  courier_enabled: true,
  cash_on_delivery_enabled: true,
  monobank_enabled: true,
  novapay_enabled: true,
  liqpay_enabled: true,
};

export function CheckoutMethodsPage() {
  const t = useTranslations("backoffice.common.checkoutMethods");
  const { showApiError, showSuccess } = useBackofficeFeedback();
  const queryFn = useCallback((token: string) => getCheckoutMethodSettings(token), []);
  const settingsState = useBackofficeQuery(queryFn, []);
  const [form, setForm] = useState<CheckoutMethodSettings>(EMPTY_SETTINGS);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (settingsState.data) {
      setForm(settingsState.data);
    }
  }, [settingsState.data]);

  const hasDelivery = useMemo(() => DELIVERY_FIELDS.some((field) => form[field]), [form]);
  const hasPayment = useMemo(() => PAYMENT_FIELDS.some((field) => form[field]), [form]);
  const isDirty = useMemo(() => {
    if (!settingsState.data) {
      return false;
    }
    return Object.keys(EMPTY_SETTINGS).some((field) => {
      const key = field as MethodField;
      return Boolean(settingsState.data?.[key]) !== Boolean(form[key]);
    });
  }, [form, settingsState.data]);

  const toggleField = useCallback((field: MethodField) => {
    setForm((prev) => ({ ...prev, [field]: !prev[field] }));
  }, []);

  const save = useCallback(async () => {
    if (!settingsState.token || isSaving || !hasDelivery || !hasPayment) {
      return;
    }

    setIsSaving(true);
    try {
      const next = await updateCheckoutMethodSettings(settingsState.token, form);
      setForm(next);
      showSuccess(t("messages.saved"));
      await settingsState.refetch();
    } catch (error) {
      showApiError(error, t("messages.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }, [form, hasDelivery, hasPayment, isSaving, settingsState, showApiError, showSuccess, t]);

  const reset = useCallback(() => {
    setForm(settingsState.data || EMPTY_SETTINGS);
  }, [settingsState.data]);

  return (
    <AsyncState
      isLoading={settingsState.isLoading}
      error={settingsState.error}
      empty={false}
      emptyLabel=""
    >
      <section className="grid gap-4">
        <PageHeader
          title={t("title")}
          description={t("subtitle")}
          actions={(
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="h-9 rounded-md border px-3 text-xs font-semibold"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                onClick={reset}
                disabled={!isDirty || isSaving}
              >
                {t("actions.reset")}
              </button>
              <button
                type="button"
                className="h-9 rounded-md border px-3 text-xs font-semibold"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                onClick={() => {
                  void save();
                }}
                disabled={!isDirty || isSaving || !hasDelivery || !hasPayment}
              >
                {isSaving ? t("actions.saving") : t("actions.save")}
              </button>
            </div>
          )}
        />

        {(!hasDelivery || !hasPayment) ? (
          <div className="rounded-md border px-3 py-2 text-sm" style={{ borderColor: "#f59e0b", backgroundColor: "color-mix(in srgb, #f59e0b 10%, var(--surface))" }}>
            {!hasDelivery ? t("messages.needDelivery") : t("messages.needPayment")}
          </div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-2">
          <MethodGroup
            title={t("delivery.title")}
            description={t("delivery.description")}
            fields={DELIVERY_FIELDS}
            form={form}
            t={t}
            onToggle={toggleField}
          />
          <MethodGroup
            title={t("payment.title")}
            description={t("payment.description")}
            fields={PAYMENT_FIELDS}
            form={form}
            t={t}
            onToggle={toggleField}
          />
        </div>
      </section>
    </AsyncState>
  );
}

function MethodGroup({
  title,
  description,
  fields,
  form,
  t,
  onToggle,
}: {
  title: string;
  description: string;
  fields: MethodField[];
  form: CheckoutMethodSettings;
  t: Translator;
  onToggle: (field: MethodField) => void;
}) {
  return (
    <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <h2 className="text-sm font-semibold">{title}</h2>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{description}</p>
      <div className="mt-3 grid gap-2">
        {fields.map((field) => (
          <MethodToggle
            key={field}
            field={field}
            checked={form[field]}
            title={t(`fields.${field}.title`)}
            description={t(`fields.${field}.description`)}
            onToggle={() => onToggle(field)}
          />
        ))}
      </div>
    </section>
  );
}

function MethodToggle({
  field,
  checked,
  title,
  description,
  onToggle,
}: {
  field: MethodField;
  checked: boolean;
  title: string;
  description: string;
  onToggle: () => void;
}) {
  const Icon = PAYMENT_FIELDS.includes(field) ? CreditCard : field === "pickup_enabled" ? Store : Truck;
  return (
    <label
      className="grid min-h-[4.25rem] grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-md border px-3 py-2"
      style={{ borderColor: checked ? "var(--accent)" : "var(--border)", backgroundColor: checked ? "color-mix(in srgb, var(--accent) 8%, var(--surface-2))" : "var(--surface-2)" }}
    >
      <span className="inline-flex h-9 w-9 items-center justify-center rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <Icon size={17} />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold">{title}</span>
        <span className="block text-xs" style={{ color: "var(--muted)" }}>{description}</span>
      </span>
      <input type="checkbox" className="h-4 w-4" checked={checked} onChange={onToggle} />
    </label>
  );
}
