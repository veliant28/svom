"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";

import { AutoDbMatchingDashboardTab } from "@/features/backoffice/components/autodb-matching/dashboard-tab";
import { AutoDbMatchingProductsTab } from "@/features/backoffice/components/autodb-matching/products-tab";
import { AutoDbMatchingSearchTab } from "@/features/backoffice/components/autodb-matching/search-tab";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import type { AutoDbProductJob } from "@/features/backoffice/types/backoffice";

type TabKey = "dashboard" | "products" | "search";

const TABS: TabKey[] = ["dashboard", "products", "search"];

export function AutoDbMatchingPage() {
  const t = useTranslations("backoffice.autodbMatching");
  const tDashboard = useTranslations("backoffice.dashboard");
  const [tab, setTab] = useState<TabKey>("dashboard");
  const [seedJob, setSeedJob] = useState<AutoDbProductJob | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const title =
    tab === "dashboard"
      ? t("tabs.dashboardTitle")
      : tab === "products"
        ? t("tabs.productsTitle")
        : t("tabs.searchTitle");

  return (
    <section>
      <PageHeader
        title={title}
        actions={(
          <button
            type="button"
            className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => setRefreshNonce((prev) => prev + 1)}
          >
            <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
            {tDashboard("actions.refreshOperationalContour")}
          </button>
        )}
        switcher={(
          <div
            className="inline-flex items-center gap-2 rounded-xl border p-1"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            role="tablist"
            aria-label={t("tabs.dashboard")}
          >
            {TABS.map((item) => {
              const active = tab === item;
              const accent =
                item === "dashboard"
                  ? "#16a34a"
                  : item === "products"
                    ? "#2563eb"
                    : "#ea580c";
              return (
                <button
                  key={item}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  className="inline-flex h-10 items-center rounded-lg border px-4 text-sm font-semibold transition-colors"
                  style={{
                    borderColor: active ? accent : "var(--border)",
                    backgroundColor: active ? accent : "var(--surface-2)",
                    color: active ? "#ffffff" : "var(--text)",
                  }}
                  onClick={() => setTab(item)}
                >
                  {t(`tabs.${item}`)}
                </button>
              );
            })}
          </div>
        )}
      />
      {tab === "dashboard" ? <AutoDbMatchingDashboardTab refreshNonce={refreshNonce} /> : null}
      {tab === "products" ? (
        <AutoDbMatchingProductsTab
          refreshNonce={refreshNonce}
          onSearchProduct={(job) => {
            setSeedJob(job);
            setTab("search");
          }}
        />
      ) : null}
      {tab === "search" ? <AutoDbMatchingSearchTab seedJob={seedJob} refreshNonce={refreshNonce} /> : null}
    </section>
  );
}
