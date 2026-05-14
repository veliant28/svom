"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useTranslations } from "next-intl";

import { getAutoDbMatchingDashboard } from "@/features/backoffice/api/backoffice-api";
import { AutoDbQuotaCard } from "@/features/backoffice/components/autodb-matching/quota-card";
import { EchartsPanel } from "@/features/backoffice/components/widgets/echarts-panel";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { AutoDbDashboard, AutoDbRemoteQuota } from "@/features/backoffice/types/backoffice";

function toCount(value: number | string | undefined): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function AutoDbMatchingDashboardTab({ refreshNonce = 0 }: { refreshNonce?: number }) {
  const t = useTranslations("backoffice.autodbMatching");
  const { showWarning } = useBackofficeFeedback();
  const queryFn = useCallback((token: string) => getAutoDbMatchingDashboard(token), []);
  const { data, isLoading, error, refetch } = useBackofficeQuery<AutoDbDashboard>(queryFn);
  const quotaPausedNotifiedRef = useRef(false);
  const charts = useDashboardCharts(data, t);
  const cards = data?.cards ?? {};
  const quotaMeta = {
    mappedBrands: toCount(cards.mapped_brands as number | string | undefined),
    totalBrands: toCount(cards.total_brands as number | string | undefined),
    linkedProducts: toCount(cards.linked_products as number | string | undefined),
    totalProducts: toCount(cards.total_products as number | string | undefined),
  };

  useEffect(() => {
    if (refreshNonce <= 0) {
      return;
    }
    void refetch();
  }, [refreshNonce, refetch]);

  const handleQuotaChange = useCallback(
    (quota: AutoDbRemoteQuota | null) => {
      const paused = quota?.status === "quota_paused";
      if (paused && !quotaPausedNotifiedRef.current) {
        showWarning(t("quota.remoteDisabled"));
      }
      quotaPausedNotifiedRef.current = paused;
    },
    [showWarning, t],
  );

  return (
    <AsyncState isLoading={isLoading} error={error} empty={!data} emptyLabel={t("states.empty")}>
      {data ? (
        <div className="grid h-[calc(100vh-11rem)] min-h-[560px] grid-rows-[auto_minmax(0,1fr)] gap-3 overflow-hidden">
          <AutoDbQuotaCard refreshNonce={refreshNonce} quotaMeta={quotaMeta} onQuotaChange={handleQuotaChange} />

          <section className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-2 rounded-2xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <h2 className="text-sm font-semibold">{t("tabs.dashboardTitle")}</h2>
            <div className="grid min-h-0 gap-3 xl:grid-cols-[0.95fr_1.05fr]">
              <div className="flex min-h-0 flex-col gap-1">
                <p className="text-xs font-semibold uppercase tracking-[0.12em]" style={{ color: "var(--muted)" }}>
                  {t("dashboard.charts.brandCoverage")}
                </p>
                <div className="min-h-0 flex-1">
                  <EchartsPanel option={charts.brandOption} hasData={charts.brandHasData} emptyLabel={t("states.empty")} className="h-full w-full" />
                </div>
              </div>

              <div className="flex min-h-0 flex-col gap-1">
                <p className="text-xs font-semibold uppercase tracking-[0.12em]" style={{ color: "var(--muted)" }}>
                  {t("dashboard.charts.funnel")}
                </p>
                <div className="min-h-0 flex-1">
                  <EchartsPanel option={charts.funnelOption} hasData={charts.funnelHasData} emptyLabel={t("states.empty")} className="h-full w-full" />
                </div>
              </div>
            </div>
          </section>
        </div>
      ) : null}
    </AsyncState>
  );
}

function useDashboardCharts(data: AutoDbDashboard | null, t: ReturnType<typeof useTranslations>) {
  return useMemo(() => {
    const brands = data?.brand_coverage_distribution ?? [];
    const brandLabels = brands.map((item) => item.label);
    const brandValues = brands.map((item) => Number(item.value ?? 0));

    const funnel = data?.matching_funnel ?? [];
    const funnelLabels = funnel.map((item) => {
      const key = String(item.stage || "").trim().toLowerCase();
      if (!key) {
        return "-";
      }
      try {
        return t(`dashboard.funnelStages.${key}` as never);
      } catch {
        return key;
      }
    });
    const funnelValues = funnel.map((item) => Number(item.count ?? 0));

    return {
      brandHasData: brands.length > 0,
      brandOption: {
        animationDuration: 320,
        grid: { left: 20, right: 20, top: 10, bottom: 28, containLabel: true },
        xAxis: {
          type: "category",
          data: brandLabels,
          axisLabel: {
            color: "#475569",
            fontSize: 10,
            interval: 0,
            hideOverlap: false,
            rotate: 0,
            margin: 6,
            lineHeight: 11,
            formatter: (value: string) => {
              const normalized = String(value ?? "");
              if (normalized.length <= 14) {
                return normalized;
              }
              const firstLine = normalized.slice(0, 14);
              const secondLine = normalized.slice(14, 28);
              return secondLine ? `${firstLine}\n${secondLine}` : firstLine;
            },
          },
        },
        yAxis: {
          type: "value",
          axisLabel: { color: "#64748b", fontSize: 11 },
          splitLine: { lineStyle: { color: "#e2e8f0" } },
        },
        series: [
          {
            name: t("dashboard.charts.brandCoverage"),
            type: "bar",
            data: brandValues,
            itemStyle: { color: "#16a34a", borderRadius: [5, 5, 0, 0] },
            barMaxWidth: 26,
          },
        ],
      },
      funnelHasData: funnel.length > 0,
      funnelOption: {
        animationDuration: 320,
        grid: { left: 20, right: 20, top: 10, bottom: 24, containLabel: true },
        xAxis: {
          type: "category",
          data: funnelLabels,
          axisLabel: { color: "#64748b", fontSize: 10, rotate: 12 },
        },
        yAxis: {
          type: "value",
          axisLabel: { color: "#64748b", fontSize: 11 },
          splitLine: { lineStyle: { color: "#e2e8f0" } },
        },
        series: [
          {
            name: t("dashboard.charts.funnel"),
            type: "line",
            smooth: 0.3,
            symbolSize: 6,
            data: funnelValues,
            lineStyle: { color: "#7c3aed", width: 2 },
            areaStyle: { color: "rgba(124,58,237,0.12)" },
            itemStyle: { color: "#7c3aed" },
          },
        ],
      },
    };
  }, [data, t]);
}
