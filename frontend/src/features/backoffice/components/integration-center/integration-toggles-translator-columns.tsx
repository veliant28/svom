"use client";

import { Globe, KeyRound, LoaderCircle, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { IntegrationToggleItem } from "@/features/backoffice/components/integration-center/integration-toggle-item";
import {
  DELIVERY_GROUP,
  PAYMENTS_GROUP,
  SUPPLIERS_GROUP,
  SYSTEM_GROUP,
  TELEGRAM_GROUP,
  TRANSLATOR_PROVIDERS,
  type ToggleConfig,
} from "@/features/backoffice/lib/integration-center.config";
import type { BackofficeIntegrationTranslatorState, IntegrationTranslatorProvider } from "@/features/backoffice/types/integration-center.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

function GroupCard({
  title,
  icon: Icon,
  items,
}: {
  title: string;
  icon: LucideIcon;
  items: ReactNode;
}) {
  return (
    <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
        <Icon size={16} />
        <span>{title}</span>
      </p>
      <div className="grid gap-2">{items}</div>
    </article>
  );
}

export function IntegrationTogglesTranslatorColumns({
  t,
  renderToggleItem,
  translator,
  isUpdatingTranslatorProvider,
  onTranslatorProvider,
  googleApiKey,
  setGoogleApiKey,
  isUpdatingGoogleApiKey,
  onGoogleApiKeyCommit,
}: {
  t: Translator;
  renderToggleItem: (item: ToggleConfig) => ReactNode;
  translator: BackofficeIntegrationTranslatorState | null;
  isUpdatingTranslatorProvider: boolean;
  onTranslatorProvider: (provider: IntegrationTranslatorProvider) => void;
  googleApiKey: string;
  setGoogleApiKey: (value: string) => void;
  isUpdatingGoogleApiKey: boolean;
  onGoogleApiKeyCommit: () => void;
}) {
  return (
    <>
      <div className="grid gap-3">
        <GroupCard title={t(PAYMENTS_GROUP.titleKey)} icon={PAYMENTS_GROUP.icon} items={PAYMENTS_GROUP.items.map((item) => renderToggleItem(item))} />
        <GroupCard title={t(DELIVERY_GROUP.titleKey)} icon={DELIVERY_GROUP.icon} items={DELIVERY_GROUP.items.map((item) => renderToggleItem(item))} />
        <GroupCard title={t(SYSTEM_GROUP.titleKey)} icon={SYSTEM_GROUP.icon} items={SYSTEM_GROUP.items.map((item) => renderToggleItem(item))} />
      </div>

      <div className="grid gap-3">
        <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
            <Globe size={16} />
            <span>{t("integrationCenter.groups.translator")}</span>
          </p>
          <div className="grid gap-2">
            {TRANSLATOR_PROVIDERS.map((provider) => {
              const isChecked = translator?.provider === provider.key;
              return (
                <IntegrationToggleItem
                  key={provider.key}
                  item={provider}
                  checked={isChecked}
                  isUpdating={isUpdatingTranslatorProvider}
                  onToggle={() => {
                    onTranslatorProvider(provider.key);
                  }}
                  t={t}
                />
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
                  onBlur={onGoogleApiKeyCommit}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      onGoogleApiKeyCommit();
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

        <GroupCard title={t(TELEGRAM_GROUP.titleKey)} icon={TELEGRAM_GROUP.icon} items={TELEGRAM_GROUP.items.map((item) => renderToggleItem(item))} />
        <GroupCard title={t(SUPPLIERS_GROUP.titleKey)} icon={SUPPLIERS_GROUP.icon} items={SUPPLIERS_GROUP.items.map((item) => renderToggleItem(item))} />
      </div>
    </>
  );
}
