"use client";

import {
  Banknote,
  Check,
  Box,
  Copy,
  CreditCard,
  Globe2,
  KeyRound,
  Languages,
  LoaderCircle,
  Mail,
  ReceiptText,
  Send,
  Store,
  Truck,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getBackofficeIntegrationCenterState,
  patchBackofficeIntegrationCenterAutoDbRemote,
  patchBackofficeIntegrationCenterToggle,
  patchBackofficeIntegrationCenterTranslator,
  postBackofficeIntegrationCenterAutoDbRemoteTestConnection,
} from "@/features/backoffice/api/integration-center-api";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import type {
  BackofficeAutoDbRemoteState,
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

type AutoDbRemoteField = "remote_host" | "remote_port" | "remote_database" | "remote_user" | "remote_password" | "image_base_url";

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

const PAYMENTS_GROUP = GROUPS[0];
const DELIVERY_GROUP = GROUPS[1];
const SUPPLIERS_GROUP = GROUPS[2];
const SYSTEM_GROUP = GROUPS[3];

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

const TELEGRAM_GROUP: ToggleGroupConfig = {
  titleKey: "integrationCenter.groups.telegram",
  icon: Send,
  items: [
    { key: "integration.telegram", labelKey: "integrationCenter.items.integrationTelegram.label", hintKey: "integrationCenter.items.integrationTelegram.hint", icon: Send },
    { key: "integration.telegram_ops", labelKey: "integrationCenter.items.integrationTelegramOps.label", hintKey: "integrationCenter.items.integrationTelegramOps.hint", icon: Send },
    { key: "integration.telegram_support", labelKey: "integrationCenter.items.integrationTelegramSupport.label", hintKey: "integrationCenter.items.integrationTelegramSupport.hint", icon: Send },
    { key: "integration.telegram_system", labelKey: "integrationCenter.items.integrationTelegramSystem.label", hintKey: "integrationCenter.items.integrationTelegramSystem.hint", icon: Send },
  ],
};

export function IntegrationCenterPage() {
  const t = useTranslations("backoffice.common");
  const { token } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();
  const [state, setState] = useState<BackofficeIntegrationCenterState | null>(null);
  const [translator, setTranslator] = useState<BackofficeIntegrationTranslatorState | null>(null);
  const [autodbRemote, setAutodbRemote] = useState<BackofficeAutoDbRemoteState | null>(null);
  const [googleApiKey, setGoogleApiKey] = useState("");
  const [autodbDraft, setAutodbDraft] = useState<Record<AutoDbRemoteField, string>>({
    remote_host: "",
    remote_port: "",
    remote_database: "",
    remote_user: "",
    remote_password: "",
    image_base_url: "",
  });
  const [autodbDirty, setAutodbDirty] = useState<Record<AutoDbRemoteField, boolean>>({
    remote_host: false,
    remote_port: false,
    remote_database: false,
    remote_user: false,
    remote_password: false,
    image_base_url: false,
  });
  const [isUpdatingTranslatorProvider, setIsUpdatingTranslatorProvider] = useState(false);
  const [isUpdatingGoogleApiKey, setIsUpdatingGoogleApiKey] = useState(false);
  const [updatingAutoDbFields, setUpdatingAutoDbFields] = useState<Record<AutoDbRemoteField, boolean>>({
    remote_host: false,
    remote_port: false,
    remote_database: false,
    remote_user: false,
    remote_password: false,
    image_base_url: false,
  });
  const [copiedField, setCopiedField] = useState<AutoDbRemoteField | "google_api_key" | null>(null);
  const [isTestingAutoDbConnection, setIsTestingAutoDbConnection] = useState(false);
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
        setAutodbRemote(payload.autodb_remote);
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

  useEffect(() => {
    if (!autodbRemote) {
      return;
    }
    setAutodbDraft({
      remote_host: autodbRemote.remote_host || "",
      remote_port: String(autodbRemote.remote_port || 3306),
      remote_database: autodbRemote.remote_database || "",
      remote_user: autodbRemote.remote_user || "",
      remote_password: autodbRemote.remote_password || "",
      image_base_url: autodbRemote.image_base_url || "",
    });
    setAutodbDirty({
      remote_host: false,
      remote_port: false,
      remote_database: false,
      remote_user: false,
      remote_password: false,
      image_base_url: false,
    });
  }, [autodbRemote]);

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
      setAutodbRemote(payload.autodb_remote);
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
      setAutodbRemote(payload.autodb_remote);
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
      setAutodbRemote(payload.autodb_remote);
      setGoogleApiKey("");
      showSuccess(t("integrationCenter.messages.translatorTokenUpdated"));
    } catch (patchError) {
      showApiError(patchError, t("integrationCenter.messages.translatorUpdateFailed"));
    } finally {
      setIsUpdatingGoogleApiKey(false);
    }
  }

  function handleAutoDbDraftChange(field: AutoDbRemoteField, value: string) {
    setAutodbDraft((prev) => ({ ...prev, [field]: value }));
    setAutodbDirty((prev) => ({ ...prev, [field]: true }));
  }

  async function handleAutoDbRemoteCommit(field: AutoDbRemoteField) {
    if (!token || !autodbRemote || updatingAutoDbFields[field] || !autodbDirty[field]) {
      return;
    }
    const rawValue = autodbDraft[field];
    const value = rawValue.trim();
    let payload: Parameters<typeof patchBackofficeIntegrationCenterAutoDbRemote>[1] | null = null;
    if (field === "remote_port") {
      const parsed = Number.parseInt(value, 10);
      if (!Number.isFinite(parsed) || parsed < 1) {
        showApiError(new Error("invalid_port"), t("integrationCenter.messages.autodbRemoteInvalidPort"));
        return;
      }
      if (parsed === autodbRemote.remote_port) {
        setAutodbDirty((prev) => ({ ...prev, [field]: false }));
        return;
      }
      payload = { remote_port: parsed };
    } else if (field === "remote_user") {
      if (!value) {
        return;
      }
      payload = { remote_user: value };
    } else if (field === "remote_password") {
      if (!value) {
        return;
      }
      payload = { remote_password: value };
    } else {
      const current = String(autodbRemote[field] || "").trim();
      if (value === current) {
        setAutodbDirty((prev) => ({ ...prev, [field]: false }));
        return;
      }
      payload = { [field]: value } as Parameters<typeof patchBackofficeIntegrationCenterAutoDbRemote>[1];
    }

    if (!payload) {
      return;
    }

    setUpdatingAutoDbFields((prev) => ({ ...prev, [field]: true }));
    try {
      const response = await patchBackofficeIntegrationCenterAutoDbRemote(token, payload);
      setState(response.state);
      setTranslator(response.translator);
      setAutodbRemote(response.autodb_remote);
      setAutodbDirty((prev) => ({ ...prev, [field]: false }));
      showSuccess(t("integrationCenter.messages.autodbRemoteUpdated"));
    } catch (patchError) {
      showApiError(patchError, t("integrationCenter.messages.autodbRemoteUpdateFailed"));
    } finally {
      setUpdatingAutoDbFields((prev) => ({ ...prev, [field]: false }));
    }
  }

  async function handleCopyField(field: AutoDbRemoteField | "google_api_key", value: string) {
    const clean = String(value || "").trim();
    if (!clean) {
      showApiError(new Error("empty_value"), t("integrationCenter.messages.copyEmpty"));
      return;
    }
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(clean);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = clean;
        textarea.setAttribute("readonly", "true");
        textarea.style.position = "fixed";
        textarea.style.left = "-9999px";
        document.body.appendChild(textarea);
        textarea.select();
        const copied = document.execCommand("copy");
        document.body.removeChild(textarea);
        if (!copied) {
          throw new Error("copy_fallback_failed");
        }
      }
      setCopiedField(field);
      showSuccess(t("integrationCenter.messages.copySuccess"));
      setTimeout(() => setCopiedField((current) => (current === field ? null : current)), 1200);
    } catch (copyError) {
      showApiError(copyError, t("integrationCenter.messages.copyFailed"));
    }
  }

  async function handleAutoDbConnectionTest() {
    if (!token || isTestingAutoDbConnection) {
      return;
    }
    setIsTestingAutoDbConnection(true);
    try {
      const response = await postBackofficeIntegrationCenterAutoDbRemoteTestConnection(token);
      if (response.ok) {
        showSuccess(t("integrationCenter.messages.autodbRemoteConnectionOk"));
      } else {
        showApiError(new Error(response.message), response.message || t("integrationCenter.messages.autodbRemoteConnectionFailed"));
      }
    } catch (testError) {
      showApiError(testError, t("integrationCenter.messages.autodbRemoteConnectionFailed"));
    } finally {
      setIsTestingAutoDbConnection(false);
    }
  }

  function renderToggleItem(item: ToggleConfig) {
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
  }

  return (
    <AsyncState isLoading={isLoading} error={error} empty={isEmpty} emptyLabel={t("integrationCenter.messages.empty")}>
      <section className="grid gap-4">
        <PageHeader title={t("integrationCenter.title")} description={t("integrationCenter.subtitle")} />

        <div className="grid gap-3 xl:grid-cols-3">
          <div className="grid gap-3">
            <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
                <PAYMENTS_GROUP.icon size={16} />
                <span>{t(PAYMENTS_GROUP.titleKey)}</span>
              </p>
              <div className="grid gap-2">{PAYMENTS_GROUP.items.map((item) => renderToggleItem(item))}</div>
            </article>

            <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
                <DELIVERY_GROUP.icon size={16} />
                <span>{t(DELIVERY_GROUP.titleKey)}</span>
              </p>
              <div className="grid gap-2">{DELIVERY_GROUP.items.map((item) => renderToggleItem(item))}</div>
            </article>

            <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
                <SYSTEM_GROUP.icon size={16} />
                <span>{t(SYSTEM_GROUP.titleKey)}</span>
              </p>
              <div className="grid gap-2">{SYSTEM_GROUP.items.map((item) => renderToggleItem(item))}</div>
            </article>
          </div>

          <div className="grid gap-3">
            <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
                <Languages size={16} />
                <span>{t("integrationCenter.groups.translator")}</span>
              </p>
              <div className="grid gap-2">
                {TRANSLATOR_PROVIDERS.map((provider) => {
                  const isChecked = translator?.provider === provider.key;
                  return (
                    <BackofficeTooltip key={provider.key} content={t(provider.hintKey)} placement="top" align="center" wrapperClassName="block">
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
                          <input type="checkbox" checked={isChecked} readOnly tabIndex={-1} className="pointer-events-none h-4 w-4" />
                        </span>
                      </button>
                    </BackofficeTooltip>
                  );
                })}

                <BackofficeTooltip content={t("integrationCenter.translator.googleToken.hint")} placement="top" align="center" wrapperClassName="block">
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

            <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
                <TELEGRAM_GROUP.icon size={16} />
                <span>{t(TELEGRAM_GROUP.titleKey)}</span>
              </p>
              <div className="grid gap-2">{TELEGRAM_GROUP.items.map((item) => renderToggleItem(item))}</div>
            </article>

            <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
                <SUPPLIERS_GROUP.icon size={16} />
                <span>{t(SUPPLIERS_GROUP.titleKey)}</span>
              </p>
              <div className="grid gap-2">{SUPPLIERS_GROUP.items.map((item) => renderToggleItem(item))}</div>
            </article>
          </div>
          <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
              <Globe2 size={16} />
              <span>{t("integrationCenter.groups.autodbRemote")}</span>
            </p>
            {!autodbRemote?.has_schema ? (
              <p className="text-xs" style={{ color: "var(--muted)" }}>{t("integrationCenter.autodbRemote.schemaMissing")}</p>
            ) : (
              <div className="grid gap-2">
                <label className="flex cursor-pointer flex-col gap-1 rounded-md border px-2.5 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                  <span>{t("integrationCenter.autodbRemote.fields.remoteHost")}</span>
                  <span className="relative inline-flex w-full items-center">
                    <input
                      type="text"
                      value={autodbDraft.remote_host}
                      onChange={(event) => handleAutoDbDraftChange("remote_host", event.target.value)}
                      onBlur={() => { void handleAutoDbRemoteCommit("remote_host"); }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          void handleAutoDbRemoteCommit("remote_host");
                        }
                      }}
                      placeholder={t("integrationCenter.autodbRemote.placeholders.remoteHost")}
                      className="h-9 w-full rounded-md border px-2 pr-10"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    />
                    <button
                      type="button"
                      className="absolute right-1 inline-flex h-7 w-7 items-center justify-center rounded-md border"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      aria-label={t("integrationCenter.actions.copy")}
                      onClick={() => { void handleCopyField("remote_host", autodbDraft.remote_host || autodbRemote.remote_host); }}
                    >
                      {copiedField === "remote_host" ? <Check size={13} /> : <Copy size={13} />}
                    </button>
                    {updatingAutoDbFields.remote_host ? <LoaderCircle size={14} className="animate-spin" /> : null}
                  </span>
                </label>

                <label className="flex cursor-pointer flex-col gap-1 rounded-md border px-2.5 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                  <span>{t("integrationCenter.autodbRemote.fields.remotePort")}</span>
                  <span className="relative inline-flex w-full items-center">
                    <input
                      type="number"
                      min={1}
                      value={autodbDraft.remote_port}
                      onChange={(event) => handleAutoDbDraftChange("remote_port", event.target.value)}
                      onBlur={() => { void handleAutoDbRemoteCommit("remote_port"); }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          void handleAutoDbRemoteCommit("remote_port");
                        }
                      }}
                      placeholder={t("integrationCenter.autodbRemote.placeholders.remotePort")}
                      className="h-9 w-full rounded-md border px-2 pr-10"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    />
                    <button
                      type="button"
                      className="absolute right-1 inline-flex h-7 w-7 items-center justify-center rounded-md border"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      aria-label={t("integrationCenter.actions.copy")}
                      onClick={() => { void handleCopyField("remote_port", autodbDraft.remote_port || String(autodbRemote.remote_port)); }}
                    >
                      {copiedField === "remote_port" ? <Check size={13} /> : <Copy size={13} />}
                    </button>
                    {updatingAutoDbFields.remote_port ? <LoaderCircle size={14} className="animate-spin" /> : null}
                  </span>
                </label>

                <label className="flex cursor-pointer flex-col gap-1 rounded-md border px-2.5 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                  <span>{t("integrationCenter.autodbRemote.fields.remoteDatabase")}</span>
                  <span className="relative inline-flex w-full items-center">
                    <input
                      type="text"
                      value={autodbDraft.remote_database}
                      onChange={(event) => handleAutoDbDraftChange("remote_database", event.target.value)}
                      onBlur={() => { void handleAutoDbRemoteCommit("remote_database"); }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          void handleAutoDbRemoteCommit("remote_database");
                        }
                      }}
                      placeholder={t("integrationCenter.autodbRemote.placeholders.remoteDatabase")}
                      className="h-9 w-full rounded-md border px-2 pr-10"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    />
                    <button
                      type="button"
                      className="absolute right-1 inline-flex h-7 w-7 items-center justify-center rounded-md border"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      aria-label={t("integrationCenter.actions.copy")}
                      onClick={() => { void handleCopyField("remote_database", autodbDraft.remote_database || autodbRemote.remote_database); }}
                    >
                      {copiedField === "remote_database" ? <Check size={13} /> : <Copy size={13} />}
                    </button>
                    {updatingAutoDbFields.remote_database ? <LoaderCircle size={14} className="animate-spin" /> : null}
                  </span>
                </label>

                <label className="flex cursor-pointer flex-col gap-1 rounded-md border px-2.5 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                  <span>{t("integrationCenter.autodbRemote.fields.remoteUser")}</span>
                  <span className="relative inline-flex w-full items-center">
                    <input
                      type="password"
                      value={autodbDraft.remote_user}
                      onChange={(event) => handleAutoDbDraftChange("remote_user", event.target.value)}
                      onBlur={() => { void handleAutoDbRemoteCommit("remote_user"); }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          void handleAutoDbRemoteCommit("remote_user");
                        }
                      }}
                      placeholder={autodbRemote.remote_user_masked || t("integrationCenter.autodbRemote.placeholders.remoteUser")}
                      className="h-9 w-full rounded-md border px-2 pr-10"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    />
                    <button
                      type="button"
                      className="absolute right-1 inline-flex h-7 w-7 items-center justify-center rounded-md border"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      aria-label={t("integrationCenter.actions.copy")}
                      onClick={() => { void handleCopyField("remote_user", autodbDraft.remote_user); }}
                    >
                      {copiedField === "remote_user" ? <Check size={13} /> : <Copy size={13} />}
                    </button>
                    {updatingAutoDbFields.remote_user ? <LoaderCircle size={14} className="animate-spin" /> : null}
                  </span>
                  <span style={{ color: "var(--muted)" }}>
                    {autodbRemote.remote_user_masked
                      ? t("integrationCenter.autodbRemote.masked.remoteUser", { value: autodbRemote.remote_user_masked })
                      : t("integrationCenter.autodbRemote.empty.remoteUser")}
                  </span>
                </label>

                <label className="flex cursor-pointer flex-col gap-1 rounded-md border px-2.5 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                  <span>{t("integrationCenter.autodbRemote.fields.remotePassword")}</span>
                  <span className="relative inline-flex w-full items-center">
                    <input
                      type="password"
                      value={autodbDraft.remote_password}
                      onChange={(event) => handleAutoDbDraftChange("remote_password", event.target.value)}
                      onBlur={() => { void handleAutoDbRemoteCommit("remote_password"); }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          void handleAutoDbRemoteCommit("remote_password");
                        }
                      }}
                      placeholder={autodbRemote.remote_password_masked || t("integrationCenter.autodbRemote.placeholders.remotePassword")}
                      className="h-9 w-full rounded-md border px-2 pr-10"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    />
                    <button
                      type="button"
                      className="absolute right-1 inline-flex h-7 w-7 items-center justify-center rounded-md border"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      aria-label={t("integrationCenter.actions.copy")}
                      onClick={() => { void handleCopyField("remote_password", autodbDraft.remote_password); }}
                    >
                      {copiedField === "remote_password" ? <Check size={13} /> : <Copy size={13} />}
                    </button>
                    {updatingAutoDbFields.remote_password ? <LoaderCircle size={14} className="animate-spin" /> : null}
                  </span>
                  <span style={{ color: "var(--muted)" }}>
                    {autodbRemote.remote_password_masked
                      ? t("integrationCenter.autodbRemote.masked.remotePassword", { value: autodbRemote.remote_password_masked })
                      : t("integrationCenter.autodbRemote.empty.remotePassword")}
                  </span>
                </label>

                <label className="flex cursor-pointer flex-col gap-1 rounded-md border px-2.5 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                  <span>{t("integrationCenter.autodbRemote.fields.imageBaseUrl")}</span>
                  <span className="relative inline-flex w-full items-center">
                    <input
                      type="text"
                      value={autodbDraft.image_base_url}
                      onChange={(event) => handleAutoDbDraftChange("image_base_url", event.target.value)}
                      onBlur={() => { void handleAutoDbRemoteCommit("image_base_url"); }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          void handleAutoDbRemoteCommit("image_base_url");
                        }
                      }}
                      placeholder={t("integrationCenter.autodbRemote.placeholders.imageBaseUrl")}
                      className="h-9 w-full rounded-md border px-2 pr-10"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    />
                    <button
                      type="button"
                      className="absolute right-1 inline-flex h-7 w-7 items-center justify-center rounded-md border"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      aria-label={t("integrationCenter.actions.copy")}
                      onClick={() => { void handleCopyField("image_base_url", autodbDraft.image_base_url || autodbRemote.image_base_url); }}
                    >
                      {copiedField === "image_base_url" ? <Check size={13} /> : <Copy size={13} />}
                    </button>
                    {updatingAutoDbFields.image_base_url ? <LoaderCircle size={14} className="animate-spin" /> : null}
                  </span>
                </label>

                <button
                  type="button"
                  className="inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  onClick={() => {
                    void handleAutoDbConnectionTest();
                  }}
                  disabled={isTestingAutoDbConnection}
                >
                  {isTestingAutoDbConnection ? <LoaderCircle size={14} className="animate-spin" /> : null}
                  <span>{t("integrationCenter.actions.testConnection")}</span>
                </button>
              </div>
            )}
          </article>
        </div>
      </section>
    </AsyncState>
  );
}
