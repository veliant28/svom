"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { MonobankRatesCard } from "@/features/backoffice/components/payment/monobank-rates-card";
import { MonobankSettingsForm } from "@/features/backoffice/components/payment/monobank-settings-form";
import { NovaPaySettingsForm } from "@/features/backoffice/components/payment/novapay-settings-form";
import { PaymentProviderSwitcher } from "@/features/backoffice/components/payment/payment-provider-switcher";
import { PaymentStatusCard } from "@/features/backoffice/components/payment/payment-status-card";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useMonobankCurrency } from "@/features/backoffice/hooks/use-monobank-currency";
import { useNovaPaySettings } from "@/features/backoffice/hooks/use-novapay-settings";
import { usePaymentSettings } from "@/features/backoffice/hooks/use-payment-settings";

export function PaymentsPage() {
  const t = useTranslations("backoffice.common");
  const [provider, setProvider] = useState<"mono" | "nova">("mono");

  const settingsState = usePaymentSettings({ t });
  const currencyState = useMonobankCurrency({ t });
  const novaSettingsState = useNovaPaySettings({ t });

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
            }}
          />
        }
      />

      {provider === "nova" ? (
        <NovaPaySettingsForm
          settings={novaSettingsState.settings}
          isLoading={novaSettingsState.isLoading}
          isSaving={novaSettingsState.isSaving}
          onSave={novaSettingsState.save}
          t={t}
        />
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
            <PaymentStatusCard settings={settingsState.settings} t={t} />
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
