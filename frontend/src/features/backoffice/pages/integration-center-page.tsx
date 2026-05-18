"use client";

import {
  Banknote,
  Box,
  CreditCard,
  Globe2,
  KeyRound,
  Languages,
  LoaderCircle,
  Mail,
  ReceiptText,
  Store,
  Truck,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getBackofficeIntegrationCenterState,
  patchBackofficeIntegrationCenterToggle,
  patchBackofficeIntegrationCenterTranslator,
} from "@/features/backoffice/api/integration-center-api";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import type {
  BackofficeIntegrationCenterState,
  BackofficeIntegrationTranslatorState,
  IntegrationCenterToggleKey,
  IntegrationTranslatorProvider,
} from "@/features/backoffice/types/integration-center.types";
import { useAuth } from "@/features/auth/hooks/use-auth";

type ToggleConfig = {
  key: IntegrationCenterToggleKey;
  labelKey: string;
  hintKey: string;
  icon: LucideIcon;
};

type ToggleGroupConfig = {
  titleKey: string;
  icon: LucideIcon;
  items: ToggleConfig[];
};

type TranslatorProviderConfig = {
  key: IntegrationTranslatorProvider;
  labelKey: string;
  hintKey: string;
  icon: LucideIcon;
};

const GROUPS: ToggleGroupConfig[] = [
  {
    titleKey: "integrationCenter.groups.payments",
    icon: CreditCard,
    items: [
      { key: "payment.cash_on_delivery", labelKey: "integrationCenter.items.paymentCod.label", hintKey: "integrationCenter.items.paymentCod.hint", icon: Banknote },
      { key: "payment.monobank", labelKey: "integrationCenter.items.paymentMonobank.label", hintKey: "integrationCenter.items.paymentMonobank.hint", icon: CreditCard },
      { key: "payment.novapay", labelKey: "integrationCenter.items.paymentNovaPay.label", hintKey: "integrationCenter.items.paymentNovaPay.hint", icon: CreditCard },
      { key: "payment.liqpay", labelKey: "integrationCenter.items.paymentLiqPay.label", hintKey: "integrationCenter.items.paymentLiqPay.hint", icon: CreditCard },
    ],
  },
  {
    titleKey: "integrationCenter.groups.delivery",
    icon: Truck,
    items: [
      { key: "delivery.pickup", labelKey: "integrationCenter.items.deliveryPickup.label", hintKey: "integrationCenter.items.deliveryPickup.hint", icon: Store },
      { key: "delivery.nova_poshta", labelKey: "integrationCenter.items.deliveryNovaPoshta.label", hintKey: "integrationCenter.items.deliveryNovaPoshta.hint", icon: Box },
      { key: "delivery.courier", labelKey: "integrationCenter.items.deliveryCourier.label", hintKey: "integrationCenter.items.deliveryCourier.hint", icon: Truck },
    ],
  },
  {
    titleKey: "integrationCenter.groups.suppliers",
    icon: Box,
    items: [
      { key: "supplier.utr", labelKey: "integrationCenter.items.supplierUtr.label", hintKey: "integrationCenter.items.supplierUtr.hint", icon: Box },
      { key: "supplier.gpl", labelKey: "integrationCenter.items.supplierGpl.label", hintKey: "integrationCenter.items.supplierGpl.hint", icon: Box },
    ],
  },
  {
    titleKey: "integrationCenter.groups.system",
    icon: Globe2,
    items: [
      { key: "integration.vchasno_kasa", labelKey: "integrationCenter.items.integrationVchasno.label", hintKey: "integrationCenter.items.integrationVchasno.hint", icon: ReceiptText },
      { key: "integration.seo", labelKey: "integrationCenter.items.integrationSeo.label", hintKey: "integrationCenter.items.integrationSeo.hint", icon: Globe2 },
      { key: "integration.email", labelKey: "integrationCenter.items.integrationEmail.label", hintKey: "integrationCenter.items.integrationEmail.hint", icon: Mail },
    ],
  },
];

const TRANSLATOR_PROVIDERS: TranslatorProviderConfig[] = [
  {
    key: "google",
    labelKey: "integrationCenter.translator.providers.google.label",
    hintKey: "integrationCenter.translator.providers.google.hint",
    icon: Globe2,
  },
  {
    key: "libretranslate",
    labelKey: "integrationCenter.translator.providers.libretranslate.label",
    hintKey: "integrationCenter.translator.providers.libretranslate.hint",
    icon: Languages,
  },
];

export function IntegrationCenterPage() {
  const t = useTranslations("backoffice.common");
  const { token } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();
  const [state, setState] = useState<BackofficeIntegrationCenterState | null>(null);
  const [translator, setTranslator] = useState<BackofficeIntegrationTranslatorState | null>(null);
  const [googleApiKey, setGoogleApiKey] = useState("");
  const [isUpdatingTranslatorProvider, setIsUpdatingTranslatorProvider] = useState(false);
  const [isUpdatingGoogleApiKey, setIsUpdatingGoogleApiKey] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingKeys, setUpdatingKeys] = useState<Record<string, boolean>>({});

  useEffect(() => {
    async function load() {
      if (!token) {
        setIsLoading(false);
        setError(null);
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        const payload = await getBackofficeIntegrationCenterState(token);
        setState(payload.state);
        setTranslator(payload.translator);
      } catch (loadError) {
        setError(showApiError(loadError, t("integrationCenter.messages.loadFailed")));
      } finally {
        setIsLoading(false);
      }
    }
    void load();
  }, [showApiError, t, token]);

  useEffect(() => {
    setGoogleApiKey("");
  }, [translator?.google_api_key_masked]);

  const isEmpty = useMemo(() => !state || Object.keys(state).length === 0, [state]);

  async function handleToggle(key: IntegrationCenterToggleKey, enabled: boolean) {
    if (!token || !state || updatingKeys[key]) {
      return;
    }
    const previousState = state;
    setUpdatingKeys((prev) => ({ ...prev, [key]: true }));
    setState({ ...state, [key]: enabled });
    try {
      const payload = await patchBackofficeIntegrationCenterToggle(token, key, enabled);
      setState(payload.state);
      setTranslator(payload.translator);
      showSuccess(t("integrationCenter.messages.updated"));
    } catch (patchError) {
      setState(previousState);
      showApiError(patchError, t("integrationCenter.messages.updateFailed"));
    } finally {
      setUpdatingKeys((prev) => ({ ...prev, [key]: false }));
    }
  }

  async function handleTranslatorProvider(provider: IntegrationTranslatorProvider) {
    if (!token || !translator || isUpdatingTranslatorProvider || translator.provider === provider) {
      return;
    }
    const previous = translator;
    setIsUpdatingTranslatorProvider(true);
    setTranslator({ ...translator, provider });
    try {
      const payload = await patchBackofficeIntegrationCenterTranslator(token, { provider });
      setState(payload.state);
      setTranslator(payload.translator);
      showSuccess(t("integrationCenter.messages.translatorProviderUpdated"));
    } catch (patchError) {
      setTranslator(previous);
      showApiError(patchError, t("integrationCenter.messages.translatorUpdateFailed"));
    } finally {
      setIsUpdatingTranslatorProvider(false);
    }
  }

  async function handleGoogleApiKeyCommit() {
    if (!token || isUpdatingGoogleApiKey) {
      return;
    }
    const nextKey = googleApiKey.trim();
    if (!nextKey) {
      return;
    }
    setIsUpdatingGoogleApiKey(true);
    try {
      const payload = await patchBackofficeIntegrationCenterTranslator(token, { google_api_key: nextKey });
      setState(payload.state);
      setTranslator(payload.translator);
      setGoogleApiKey("");
      showSuccess(t("integrationCenter.messages.translatorTokenUpdated"));
    } catch (patchError) {
      showApiError(patchError, t("integrationCenter.messages.translatorUpdateFailed"));
    } finally {
      setIsUpdatingGoogleApiKey(false);
    }
  }

  return (
    <AsyncState isLoading={isLoading} error={error} empty={isEmpty} emptyLabel={t("integrationCenter.messages.empty")}>
      <section className="grid gap-4">
        <PageHeader title={t("integrationCenter.title")} description={t("integrationCenter.subtitle")} />

        <div className="grid gap-3 xl:grid-cols-2 2xl:grid-cols-5">
          {GROUPS.map((group) => (
            <article key={group.titleKey} className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
                <group.icon size={16} />
                <span>{t(group.titleKey)}</span>
              </p>
              <div className="grid gap-2">
                {group.items.map((item) => {
                  const checked = Boolean(state?.[item.key]);
                  const isUpdating = Boolean(updatingKeys[item.key]);

                  return (
                    <BackofficeTooltip
                      key={item.key}
                      content={t(item.hintKey)}
                      placement="top"
                      align="center"
                      wrapperClassName="block"
                    >
                      <button
                        type="button"
                        aria-pressed={checked}
                        disabled={isUpdating}
                        className="flex w-full cursor-pointer items-center justify-between gap-2 rounded-md border px-2.5 py-2 text-left text-xs disabled:opacity-80"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        onClick={() => {
                          void handleToggle(item.key, !checked);
                        }}
                      >
                        <span className="inline-flex items-center gap-2">
                          <item.icon size={14} />
                          <span>{t(item.labelKey)}</span>
                        </span>
                        <span className="inline-flex items-center gap-2">
                          {isUpdating ? <LoaderCircle size={14} className="animate-spin" /> : null}
                          <input
                            type="checkbox"
                            checked={checked}
                            readOnly
                            tabIndex={-1}
                            className="pointer-events-none h-4 w-4"
                          />
                        </span>
                      </button>
                    </BackofficeTooltip>
                  );
                })}
              </div>
            </article>
          ))}

          <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
              <Languages size={16} />
              <span>{t("integrationCenter.groups.translator")}</span>
            </p>

            <div className="grid gap-2">
              {TRANSLATOR_PROVIDERS.map((provider) => {
                const isChecked = translator?.provider === provider.key;
                return (
                  <BackofficeTooltip
                    key={provider.key}
                    content={t(provider.hintKey)}
                    placement="top"
                    align="center"
                    wrapperClassName="block"
                  >
                    <button
                      type="button"
                      aria-pressed={isChecked}
                      disabled={isUpdatingTranslatorProvider}
                      className="flex w-full cursor-pointer items-center justify-between gap-2 rounded-md border px-2.5 py-2 text-left text-xs disabled:opacity-80"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      onClick={() => {
                        void handleTranslatorProvider(provider.key);
                      }}
                    >
                      <span className="inline-flex items-center gap-2">
                        <provider.icon size={14} />
                        <span>{t(provider.labelKey)}</span>
                      </span>
                      <span className="inline-flex items-center gap-2">
                        {isUpdatingTranslatorProvider ? <LoaderCircle size={14} className="animate-spin" /> : null}
                        <input
                          type="radio"
                          checked={isChecked}
                          readOnly
                          tabIndex={-1}
                          className="pointer-events-none h-4 w-4"
                        />
                      </span>
                    </button>
                  </BackofficeTooltip>
                );
              })}

              <BackofficeTooltip
                content={t("integrationCenter.translator.googleToken.hint")}
                placement="top"
                align="center"
                wrapperClassName="block"
              >
                <label className="flex cursor-pointer flex-col gap-1 rounded-md border px-2.5 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                  <span className="inline-flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-2">
                      <KeyRound size={14} />
                      <span>{t("integrationCenter.translator.googleToken.label")}</span>
                    </span>
                    <span className="inline-flex w-4 items-center justify-end">
                      {isUpdatingGoogleApiKey ? <LoaderCircle size={14} className="animate-spin" /> : null}
                    </span>
                  </span>
                  <input
                    type="password"
                    value={googleApiKey}
                    onChange={(event) => setGoogleApiKey(event.target.value)}
                    onBlur={() => {
                      void handleGoogleApiKeyCommit();
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        void handleGoogleApiKeyCommit();
                      }
                    }}
                    placeholder={translator?.google_api_key_masked || t("integrationCenter.translator.googleToken.placeholder")}
                    className="h-9 rounded-md border px-2"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                  />
                  <span style={{ color: "var(--muted)" }}>
                    {translator?.google_api_key_masked
                      ? t("integrationCenter.translator.googleToken.masked", { value: translator.google_api_key_masked })
                      : t("integrationCenter.translator.googleToken.empty")}
                  </span>
                </label>
              </BackofficeTooltip>
            </div>
          </article>
        </div>
      </section>
    </AsyncState>
  );
}
