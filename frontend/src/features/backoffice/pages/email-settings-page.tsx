"use client";

import { useTranslations } from "next-intl";

import { EmailSettingsForm } from "@/features/backoffice/components/email-settings/email-settings-form";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useEmailSettings } from "@/features/backoffice/hooks/use-email-settings";

export function EmailSettingsPage() {
  const t = useTranslations("backoffice.common");
  const emailSettings = useEmailSettings({ t });

  return (
    <section className="grid gap-4">
      <PageHeader title={t("email.title")} description={t("email.subtitle")} />

      <AsyncState
        isLoading={emailSettings.isLoading}
        error={null}
        empty={false}
        emptyLabel=""
      >
        <EmailSettingsForm
          settings={emailSettings.settings}
          testResult={emailSettings.testResult}
          isSaving={emailSettings.isSaving}
          isTesting={emailSettings.isTesting}
          onSave={emailSettings.save}
          onTest={emailSettings.test}
          t={t}
        />
      </AsyncState>
    </section>
  );
}
