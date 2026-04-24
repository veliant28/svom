"use client";

import { StatCard } from "@/features/backoffice/components/widgets/stat-card";
import type {
  BackofficeGoogleSettings,
  BackofficeSeoDashboard,
  BackofficeSeoSettings,
} from "@/features/backoffice/api/seo-api.types";
import type { SeoWorkspace } from "@/features/backoffice/components/seo/seo-workspace-switcher";

export function SeoSummaryCards({
  workspace,
  seoSettings,
  googleSettings,
  dashboard,
  t,
}: {
  workspace: SeoWorkspace;
  seoSettings: BackofficeSeoSettings | null;
  googleSettings: BackofficeGoogleSettings | null;
  dashboard: BackofficeSeoDashboard | null;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  if (workspace === "google") {
    return (
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <StatCard title={t("seo.summary.googleEnabled")} value={googleSettings?.is_enabled ? t("yes") : t("no")} />
        <StatCard title={t("seo.summary.ga4")} value={dashboard?.ga4_configured ? t("seo.status.configured") : t("seo.status.notConfigured")} />
        <StatCard title={t("seo.summary.gtm")} value={dashboard?.gtm_configured ? t("seo.status.configured") : t("seo.status.notConfigured")} />
        <StatCard title={t("seo.summary.searchConsole")} value={dashboard?.search_console_configured ? t("seo.status.configured") : t("seo.status.notConfigured")} />
        <StatCard
          title={t("seo.summary.ecommerceEvents")}
          value={googleSettings?.ecommerce_events_enabled ? t("yes") : t("no")}
        />
      </div>
    );
  }

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
      <StatCard title={t("seo.summary.seoEnabled")} value={seoSettings?.is_enabled ? t("yes") : t("no")} />
      <StatCard title={t("seo.summary.sitemap")} value={seoSettings?.sitemap_enabled ? t("yes") : t("no")} />
      <StatCard title={t("seo.summary.robots")} value={seoSettings?.default_robots_directive || "-"} />
      <StatCard title={t("seo.summary.templates")} value={dashboard?.active_templates_count ?? 0} />
      <StatCard title={t("seo.summary.overrides")} value={dashboard?.active_overrides_count ?? 0} />
      <StatCard
        title={t("seo.summary.missingMeta")}
        value={dashboard?.missing_meta_available ? dashboard?.missing_meta_by_type.length ?? 0 : "-"}
        subtitle={dashboard?.missing_meta_available ? undefined : t("seo.states.metaChecksUnavailable")}
      />
    </div>
  );
}
