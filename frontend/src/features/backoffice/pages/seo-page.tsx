"use client";

import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { useTranslations } from "next-intl";

import { GoogleAnalyticsChart } from "@/features/backoffice/components/seo/google-analytics-chart";
import { GoogleEventsCard } from "@/features/backoffice/components/seo/google-events-card";
import { GoogleSettingsForm } from "@/features/backoffice/components/seo/google-settings-form";
import { GoogleVerificationCard } from "@/features/backoffice/components/seo/google-verification-card";
import { SeoHealthChart } from "@/features/backoffice/components/seo/seo-health-chart";
import { SeoMetaTemplatesForm } from "@/features/backoffice/components/seo/seo-meta-templates-form";
import { SeoOverridesForm } from "@/features/backoffice/components/seo/seo-overrides-form";
import { SeoRobotsEditor } from "@/features/backoffice/components/seo/seo-robots-editor";
import { SeoSettingsForm } from "@/features/backoffice/components/seo/seo-settings-form";
import { SeoSummaryCards } from "@/features/backoffice/components/seo/seo-summary-cards";
import { SeoSitemapCard } from "@/features/backoffice/components/seo/seo-sitemap-card";
import { SeoWorkspaceSwitcher, type SeoWorkspace } from "@/features/backoffice/components/seo/seo-workspace-switcher";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useGoogleSettings } from "@/features/backoffice/hooks/use-google-settings";
import { useSeoDashboard } from "@/features/backoffice/hooks/use-seo-dashboard";
import { useSeoSettings } from "@/features/backoffice/hooks/use-seo-settings";
import { BACKOFFICE_CAPABILITIES, hasBackofficeCapability } from "@/features/backoffice/lib/capabilities";
import { useAuth } from "@/features/auth/hooks/use-auth";

export function SeoPage() {
  const t = useTranslations("backoffice.common");
  const [workspace, setWorkspace] = useState<SeoWorkspace>("seo");
  const { user } = useAuth();
  const canManage = hasBackofficeCapability(user, BACKOFFICE_CAPABILITIES.seoManage);

  const seoState = useSeoSettings({ t });
  const googleState = useGoogleSettings({ t });
  const dashboardState = useSeoDashboard();

  const isSeoWorkspace = workspace === "seo";
  const isLoading = isSeoWorkspace
    ? seoState.isLoading || dashboardState.isLoading
    : googleState.isLoading || dashboardState.isLoading;
  const error = isSeoWorkspace
    ? seoState.loadError || dashboardState.error
    : googleState.loadError || dashboardState.error;

  return (
    <AsyncState isLoading={isLoading} error={error} empty={false} emptyLabel="">
      <section className="grid gap-4">
        <PageHeader
          title={t("seo.title")}
          description={t("seo.subtitle")}
          switcher={(
            <SeoWorkspaceSwitcher
              active={workspace}
              onChange={setWorkspace}
              ariaLabel={t("seo.switcherAria")}
              labels={{
                seo: t("seo.switcher.seo"),
                google: t("seo.switcher.google"),
              }}
            />
          )}
          actionsBeforeLogout={(
            <button
              type="button"
              className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void Promise.all([
                  seoState.reload(),
                  googleState.reload(),
                  dashboardState.refetch(),
                ]);
              }}
            >
              <RefreshCw className="h-4 w-4 animate-spin" style={{ animationDuration: "2.2s" }} />
              {t("seo.actions.refresh")}
            </button>
          )}
        />

        <SeoSummaryCards
          workspace={workspace}
          seoSettings={seoState.settings}
          googleSettings={googleState.settings}
          dashboard={dashboardState.data}
          t={t}
        />

        {isSeoWorkspace ? (
          <>
            <SeoSettingsForm
              settings={seoState.settings}
              isSaving={seoState.isSavingSettings}
              canManage={canManage}
              onSave={seoState.saveSettings}
              t={t}
            />

            <div className="grid gap-4 xl:grid-cols-2">
              <SeoSitemapCard
                settings={seoState.settings}
                lastSitemapResult={seoState.lastSitemapResult}
                isSavingSettings={seoState.isSavingSettings}
                isRebuilding={seoState.isRebuildingSitemap}
                canManage={canManage}
                onSaveSettings={seoState.saveSettings}
                onRebuild={seoState.rebuildSitemap}
                t={t}
              />
              <SeoHealthChart dashboard={dashboardState.data} t={t} />
            </div>

            <SeoRobotsEditor
              robotsValue={seoState.settings?.robots_txt || ""}
              previewValue={seoState.robotsPreview}
              isSaving={seoState.isSavingRobots}
              canManage={canManage}
              onSave={seoState.saveRobots}
              t={t}
            />

            <SeoMetaTemplatesForm
              templates={seoState.templates}
              activeActionId={seoState.activeTemplateActionId}
              canManage={canManage}
              onCreate={seoState.createTemplate}
              onUpdate={seoState.updateTemplate}
              onDelete={seoState.deleteTemplate}
              t={t}
            />

            <SeoOverridesForm
              overrides={seoState.overrides}
              activeActionId={seoState.activeOverrideActionId}
              canManage={canManage}
              onCreate={seoState.createOverride}
              onUpdate={seoState.updateOverride}
              onDelete={seoState.deleteOverride}
              t={t}
            />
          </>
        ) : (
          <>
            <div className="grid gap-4 xl:grid-cols-2">
              <GoogleSettingsForm
                settings={googleState.settings}
                isSaving={googleState.isSaving}
                canManage={canManage}
                fieldErrors={googleState.fieldErrors}
                onSave={googleState.saveSettings}
                t={t}
              />
              <GoogleVerificationCard
                settings={googleState.settings}
                isSaving={googleState.isSaving}
                canManage={canManage}
                onSave={googleState.saveSettings}
                t={t}
              />
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <GoogleEventsCard
                events={googleState.events}
                activeEventId={googleState.activeEventId}
                canManage={canManage}
                onToggle={googleState.toggleEvent}
                t={t}
              />
              <GoogleAnalyticsChart dashboard={dashboardState.data} t={t} />
            </div>
          </>
        )}
      </section>
    </AsyncState>
  );
}
