"use client";

import { useState } from "react";
import { Clock3, LoaderCircle, RefreshCw } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { AutoDbBatchHistoryModal } from "@/features/backoffice/components/autodb-matching/batch-history-modal";
import { AutoDbMatchingDashboardTab } from "@/features/backoffice/components/autodb-matching/dashboard-tab";
import { AutoDbMatchingProductsTab } from "@/features/backoffice/components/autodb-matching/products-tab";
import { AutoDbMatchingSearchTab } from "@/features/backoffice/components/autodb-matching/search-tab";
import { AutoDbMatchingTecdocApiTab } from "@/features/backoffice/components/autodb-matching/tecdoc-api-tab";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useAutoDbBatchMonitor } from "@/features/backoffice/hooks/use-autodb-batch-monitor";
import { useAutoDbTecdocApiBatchMonitor } from "@/features/backoffice/hooks/use-autodb-tecdoc-api-batch-monitor";
import type { AutoDbProductJob } from "@/features/backoffice/types/backoffice";

type TabKey = "dashboard" | "products" | "search" | "tecdocApi";

const TABS: TabKey[] = ["dashboard", "products", "search", "tecdocApi"];

export function AutoDbMatchingPage() {
  const locale = useLocale();
  const t = useTranslations("backoffice.autodbMatching");
  const tDashboard = useTranslations("backoffice.dashboard");
  const [tab, setTab] = useState<TabKey>("dashboard");
  const [seedJob, setSeedJob] = useState<AutoDbProductJob | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(false);
  const legacyBatch = useAutoDbBatchMonitor({
    refreshNonce,
    isHistoryModalOpen: historyOpen && tab !== "tecdocApi",
    enableToasts: tab !== "tecdocApi",
  });
  const apiBatch = useAutoDbTecdocApiBatchMonitor({
    refreshNonce,
    isHistoryModalOpen: historyOpen && tab === "tecdocApi",
    enableToasts: tab === "tecdocApi",
  });
  const batch = tab === "tecdocApi" ? apiBatch : legacyBatch;
  const title =
    tab === "dashboard"
      ? t("tabs.dashboardTitle")
      : tab === "products"
        ? t("tabs.productsTitle")
        : tab === "search"
          ? t("tabs.searchTitle")
          : t("tabs.tecdocApiTitle");

  return (
    <section>
      <PageHeader
        title={title}
        actions={(
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => setHistoryOpen(true)}
            >
              {batch.isRunning ? (
                <LoaderCircle size={16} className="animate-spin" />
              ) : (
                <Clock3 size={16} />
              )}
              <span className={batch.isRunning ? "animate-pulse" : ""}>{t("batchHistory.button")}</span>
            </button>

            <button
              type="button"
              className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => setRefreshNonce((prev) => prev + 1)}
            >
              <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
              {tDashboard("actions.refreshOperationalContour")}
            </button>
          </div>
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
                    : item === "search"
                      ? "#ea580c"
                      : "#0f766e";
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
          locale={locale}
          refreshNonce={refreshNonce}
          onSearchProduct={(job) => {
            setSeedJob(job);
            setTab("search");
          }}
        />
      ) : null}
      {tab === "search" ? <AutoDbMatchingSearchTab seedJob={seedJob} refreshNonce={refreshNonce} /> : null}
      {tab === "tecdocApi" ? <AutoDbMatchingTecdocApiTab monitor={apiBatch} /> : null}

      <AutoDbBatchHistoryModal
        isOpen={historyOpen}
        locale={locale}
        run={batch.run}
        remoteQuota={batch.remoteQuota}
        isRunning={batch.isRunning}
        onClose={() => setHistoryOpen(false)}
      />
    </section>
  );
}
