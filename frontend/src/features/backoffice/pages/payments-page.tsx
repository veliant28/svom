"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { MonobankRatesCard } from "@/features/backoffice/components/payment/monobank-rates-card";
import { MonobankSettingsForm } from "@/features/backoffice/components/payment/monobank-settings-form";
import { LiqPaySettingsForm } from "@/features/backoffice/components/payment/liqpay-settings-form";
import { NovaPaySettingsForm } from "@/features/backoffice/components/payment/novapay-settings-form";
import { PaymentProviderSwitcher } from "@/features/backoffice/components/payment/payment-provider-switcher";
import { PaymentStatusCard } from "@/features/backoffice/components/payment/payment-status-card";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useLiqPaySettings } from "@/features/backoffice/hooks/use-liqpay-settings";
import { useMonobankCurrency } from "@/features/backoffice/hooks/use-monobank-currency";
import { useNovaPaySettings } from "@/features/backoffice/hooks/use-novapay-settings";
import { usePaymentSettings } from "@/features/backoffice/hooks/use-payment-settings";

export function PaymentsPage() {
  const t = useTranslations("backoffice.common");
  const [provider, setProvider] = useState<"mono" | "nova" | "liq">("mono");

  const settingsState = usePaymentSettings({ t });
  const currencyState = useMonobankCurrency({ t });
  const novaSettingsState = useNovaPaySettings({ t });
  const liqpaySettingsState = useLiqPaySettings({ t });

  return (
    <section className="grid gap-4">
      <PageHeader
        title={t("payments.title")}
        description={t("payments.subtitle")}
        switcher={
          <PaymentProviderSwitcher
            active={provider}
            onChange={setProvider}
            labels={{
              mono: t("payments.providers.mono"),
              nova: t("payments.providers.nova"),
              liq: t("payments.providers.liq"),
            }}
          />
        }
      />

      {provider === "nova" ? (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
          <NovaPaySettingsForm
            settings={novaSettingsState.settings}
            isLoading={novaSettingsState.isLoading}
            isSaving={novaSettingsState.isSaving}
            isTesting={novaSettingsState.isTesting}
            onSave={novaSettingsState.save}
            onTestConnection={novaSettingsState.testConnection}
            t={t}
          />
          <PaymentStatusCard
            settings={novaSettingsState.settings}
            title={t("payments.novapay.status")}
            enabledLabel={t("payments.novapay.enabled")}
            lastConnectionLabel={t("payments.novapay.lastConnection")}
            lastConnectionStateLabel={t("payments.novapay.lastConnectionState")}
            lastConnectionMessageLabel={t("payments.novapay.lastConnectionMessage")}
            t={t}
          />
        </div>
      ) : provider === "liq" ? (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
          <LiqPaySettingsForm
            settings={liqpaySettingsState.settings}
            isLoading={liqpaySettingsState.isLoading}
            isSaving={liqpaySettingsState.isSaving}
            isTesting={liqpaySettingsState.isTesting}
            onSave={liqpaySettingsState.save}
            onTestConnection={liqpaySettingsState.testConnection}
            t={t}
          />
          <PaymentStatusCard
            settings={liqpaySettingsState.settings}
            title={t("payments.liqpay.status")}
            enabledLabel={t("payments.liqpay.enabled")}
            lastConnectionLabel={t("payments.liqpay.lastConnection")}
            lastConnectionStateLabel={t("payments.liqpay.lastConnectionState")}
            lastConnectionMessageLabel={t("payments.liqpay.lastConnectionMessage")}
            t={t}
          />
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
          <MonobankSettingsForm
            settings={settingsState.settings}
            isSaving={settingsState.isSaving}
            isTesting={settingsState.isTesting}
            onSave={settingsState.save}
            onTestConnection={settingsState.testConnection}
            t={t}
          />

          <div className="grid gap-4">
            <PaymentStatusCard
              settings={settingsState.settings}
              title={t("payments.monobank.status")}
              enabledLabel={t("payments.monobank.enabled")}
              lastConnectionLabel={t("payments.monobank.lastConnection")}
              lastConnectionStateLabel={t("payments.monobank.lastConnectionState")}
              lastConnectionMessageLabel={t("payments.monobank.lastConnectionMessage")}
              t={t}
            />
            <MonobankRatesCard
              rates={currencyState.data}
              isLoading={currencyState.isLoading}
              refreshDisabled={currencyState.isRefreshCooldown}
              onRefresh={() => {
                void currencyState.refresh();
              }}
              t={t}
            />
          </div>
        </div>
      )}
    </section>
  );
}
