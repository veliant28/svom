"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Clock3, PackageCheck, RefreshCw, TrendingUp } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";

import { getBackofficeSummary } from "@/features/backoffice/api/backoffice-api";
import { OperationsRoleSwitcher } from "@/features/backoffice/components/dashboard/operations-role-switcher";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { normalizeStatusKey, normalizeStatusLabel } from "@/features/backoffice/lib/status";
import type { BackofficeSummary } from "@/features/backoffice/types/backoffice";

const ORDER_WARNING_SECONDS = 15 * 60;
const ORDER_CRITICAL_SECONDS = 45 * 60;

function formatDuration(valueSeconds: number): string {
  const seconds = Math.max(0, Math.floor(valueSeconds));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return [hours, minutes, secs].map((part) => String(part).padStart(2, "0")).join(":");
}

function resolveUnprocessedOrdersTone(count: number, ageSeconds: number | null): "success" | "warning" | "error" {
  if (count <= 0 || ageSeconds === null) {
    return "success";
  }
  if (ageSeconds >= ORDER_CRITICAL_SECONDS) {
    return "error";
  }
  if (ageSeconds >= ORDER_WARNING_SECONDS) {
    return "warning";
  }
  return "success";
}

function formatCompactTimestamp(raw: string): string {
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(date);
}

type EChartInstance = {
  setOption: (option: object) => void;
  resize: () => void;
  dispose: () => void;
};

function DashboardEChart({
  option,
  hasData,
  emptyLabel,
}: {
  option: object;
  hasData: boolean;
  emptyLabel: string;
}) {
  const chartRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!hasData) {
      return;
    }
    let chart: EChartInstance | null = null;
    let disposed = false;

    async function mount() {
      if (!chartRef.current) {
        return;
      }
      const echarts = await import("echarts");
      if (disposed || !chartRef.current) {
        return;
      }
      chart = echarts.init(chartRef.current);
      chart.setOption(option);
    }

    void mount();

    const onResize = () => {
      chart?.resize();
    };
    window.addEventListener("resize", onResize);

    return () => {
      disposed = true;
      window.removeEventListener("resize", onResize);
      chart?.dispose();
    };
  }, [hasData, option]);

  if (!hasData) {
    return (
      <div
        className="flex h-full min-h-[200px] items-center justify-center rounded-xl border text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }}
      >
        {emptyLabel}
      </div>
    );
  }

  return <div ref={chartRef} className="h-full min-h-[200px] w-full" />;
}

function DashboardKpiCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trailing,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: LucideIcon;
  trailing?: ReactNode;
}) {
  return (
    <article className="rounded-2xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] uppercase tracking-[0.14em]" style={{ color: "var(--muted)" }}>
          {title}
        </p>
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <p className="mt-1 text-xl font-semibold">{value}</p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {subtitle}
      </p>
      {trailing ? <div className="mt-2">{trailing}</div> : null}
    </article>
  );
}

export function BackofficeDashboardPage() {
  const t = useTranslations("backoffice.dashboard");
  const tCommon = useTranslations("backoffice.common");
  const { showInfo, showWarning } = useBackofficeFeedback();
  const [nowMs, setNowMs] = useState(() => Date.now());
  const toastKeyRef = useRef("");

  const queryFn = useCallback((token: string) => getBackofficeSummary(token), []);
  const { data, isLoading, error, refetch } = useBackofficeQuery<BackofficeSummary>(queryFn);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);
    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void refetch();
    }, 60_000);
    return () => {
      window.clearInterval(intervalId);
    };
  }, [refetch]);

  const numberFormatter = useMemo(() => new Intl.NumberFormat(), []);
  const formatNumber = useCallback((value: number) => numberFormatter.format(Number.isFinite(value) ? value : 0), [numberFormatter]);

  const unprocessedCount = data?.orders_unprocessed?.count ?? 0;
  const oldestRaw = data?.orders_unprocessed?.oldest_created_at ?? null;
  const oldestMs = oldestRaw ? new Date(oldestRaw).getTime() : null;
  const oldestAgeSeconds = oldestMs !== null && Number.isFinite(oldestMs) ? Math.max(0, Math.floor((nowMs - oldestMs) / 1000)) : null;
  const unprocessedTone = resolveUnprocessedOrdersTone(unprocessedCount, oldestAgeSeconds);
  const unprocessedTimerLabel = unprocessedCount > 0 && oldestAgeSeconds !== null
    ? formatDuration(oldestAgeSeconds)
    : t("cards.unprocessedOrdersTimerIdle");

  useEffect(() => {
    if (!data || unprocessedCount <= 0) {
      toastKeyRef.current = "";
      return;
    }

    const level = unprocessedTone === "error" ? "critical" : unprocessedTone === "warning" ? "warning" : "info";
    const nextKey = `${level}:${unprocessedCount}`;
    if (toastKeyRef.current === nextKey) {
      return;
    }

    if (level === "critical") {
      showWarning(t("alerts.unprocessedOrdersCritical", { count: unprocessedCount }));
    } else if (level === "warning") {
      showWarning(t("alerts.unprocessedOrdersWarning", { count: unprocessedCount }));
    } else {
      showInfo(t("alerts.unprocessedOrdersInfo", { count: unprocessedCount }));
    }

    toastKeyRef.current = nextKey;
  }, [data, showInfo, showWarning, t, unprocessedCount, unprocessedTone]);

  const resolveStatusLabel = useCallback((status: string) => {
    const key = normalizeStatusKey(status);
    try {
      return tCommon(`statuses.${key}` as never);
    } catch {
      return normalizeStatusLabel(status);
    }
  }, [tCommon]);

  const statusItems = useMemo(
    () => (data?.status_buckets ?? []).map((item) => ({
      label: resolveStatusLabel(item.status),
      value: item.total,
    })).filter((item) => item.value > 0),
    [data?.status_buckets, resolveStatusLabel],
  );

  const qualityTrendItems = useMemo(
    () => [...(data?.quality_trend ?? [])].slice(0, 10).reverse(),
    [data?.quality_trend],
  );

  const supplierQualityItems = useMemo(
    () => [...(data?.match_rate_by_supplier ?? [])].slice(0, 6).reverse(),
    [data?.match_rate_by_supplier],
  );

  const runStatusOption = useMemo(() => ({
    animationDuration: 500,
    tooltip: { trigger: "item" },
    legend: { show: false },
    series: [
      {
        type: "pie",
        radius: ["46%", "74%"],
        center: ["50%", "52%"],
        label: { show: false },
        data: statusItems.map((item) => ({ name: item.label, value: item.value })),
        color: ["#2563eb", "#0891b2", "#16a34a", "#ca8a04", "#dc2626", "#7c3aed", "#475569"],
      },
    ],
  }), [statusItems]);

  const qualityTrendOption = useMemo(() => ({
    animationDuration: 500,
    grid: { left: 24, right: 16, top: 22, bottom: 26, containLabel: true },
    tooltip: { trigger: "axis" },
    legend: { top: 0, right: 0, textStyle: { color: "#64748b", fontSize: 11 } },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: qualityTrendItems.map((item) => formatCompactTimestamp(item.created_at)),
      axisLabel: { color: "#64748b", fontSize: 11 },
      axisLine: { lineStyle: { color: "#cbd5e1" } },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLabel: { color: "#64748b", fontSize: 11, formatter: "{value}%" },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    series: [
      {
        name: t("charts.quality.matchRate"),
        type: "line",
        smooth: true,
        symbolSize: 6,
        data: qualityTrendItems.map((item) => Number(item.match_rate)),
        lineStyle: { color: "#16a34a", width: 2 },
        areaStyle: { color: "rgba(22,163,74,0.14)" },
        itemStyle: { color: "#16a34a" },
      },
      {
        name: t("charts.quality.errorRate"),
        type: "line",
        smooth: true,
        symbolSize: 6,
        data: qualityTrendItems.map((item) => Number(item.error_rate)),
        lineStyle: { color: "#dc2626", width: 2 },
        areaStyle: { color: "rgba(220,38,38,0.12)" },
        itemStyle: { color: "#dc2626" },
      },
    ],
  }), [qualityTrendItems, t]);

  const supplierQualityOption = useMemo(() => ({
    animationDuration: 500,
    grid: { left: 18, right: 18, top: 24, bottom: 16, containLabel: true },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { top: 0, right: 0, textStyle: { color: "#64748b", fontSize: 11 } },
    xAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLabel: { color: "#64748b", fontSize: 11, formatter: "{value}%" },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    yAxis: {
      type: "category",
      data: supplierQualityItems.map((item) => item.source_code.toUpperCase()),
      axisLabel: { color: "#475569", fontSize: 11 },
      axisLine: { lineStyle: { color: "#cbd5e1" } },
    },
    series: [
      {
        name: t("charts.suppliers.matchRate"),
        type: "bar",
        barWidth: 10,
        data: supplierQualityItems.map((item) => Number(item.match_rate)),
        itemStyle: { color: "#2563eb", borderRadius: [0, 4, 4, 0] },
      },
      {
        name: t("charts.suppliers.errorRate"),
        type: "bar",
        barWidth: 10,
        data: supplierQualityItems.map((item) => Number(item.error_rate)),
        itemStyle: { color: "#f97316", borderRadius: [0, 4, 4, 0] },
      },
    ],
  }), [supplierQualityItems, t]);

  return (
    <section>
      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        switcher={(
          <OperationsRoleSwitcher
            activeTab="dashboard"
            dashboardHref="/backoffice"
            managersHref="/backoffice/operations/managers"
            operatorsHref="/backoffice/operations/operators"
            dashboardLabel={t("staff.roles.dashboard")}
            managersLabel={t("staff.roles.managers")}
            operatorsLabel={t("staff.roles.operators")}
            ariaLabel={t("staff.switcherAriaLabel")}
          />
        )}
        actions={
          <button
            type="button"
            className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              void refetch();
            }}
          >
            <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
            {t("actions.refreshOperationalContour")}
          </button>
        }
      />

      <AsyncState isLoading={isLoading} error={error} empty={!data} emptyLabel={t("states.empty")}>
        {data ? (
          <div className="grid h-[calc(100vh-11rem)] min-h-[560px] grid-rows-[auto_1fr] gap-3 overflow-hidden">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <DashboardKpiCard
                title={t("cards.unprocessedOrders")}
                value={formatNumber(unprocessedCount)}
                subtitle={
                  data.orders_unprocessed?.oldest_order_number
                    ? t("cards.unprocessedOrdersSubtitleWithOrder", { order: data.orders_unprocessed.oldest_order_number })
                    : t("cards.unprocessedOrdersSubtitle")
                }
                icon={AlertTriangle}
                trailing={(
                  <BackofficeStatusChip
                    tone={unprocessedTone}
                    palette="countdown"
                    icon={Clock3}
                    className={unprocessedTone === "warning" || unprocessedTone === "error" ? "animate-pulse" : ""}
                  >
                    {t("cards.unprocessedOrdersTimer", { value: unprocessedTimerLabel })}
                  </BackofficeStatusChip>
                )}
              />

              <DashboardKpiCard
                title={t("cards.publishedProducts")}
                value={formatNumber(data.totals.published_products)}
                subtitle={t("cards.publishedProductsSubtitle", { count: formatNumber(data.totals.product_prices) })}
                icon={PackageCheck}
              />

              <DashboardKpiCard
                title={t("cards.repriced")}
                value={formatNumber(data.totals.repriced_products_total)}
                subtitle={t("cards.repriced24h", { count: formatNumber(data.totals.repriced_products_24h) })}
                icon={TrendingUp}
              />

              <DashboardKpiCard
                title={t("cards.errors24hTitle")}
                value={formatNumber(data.totals.errors_24h)}
                subtitle={t("cards.errorsTotal", { count: formatNumber(data.totals.errors_total) })}
                icon={AlertTriangle}
              />
            </div>

            <div className="grid min-h-0 gap-3 xl:grid-cols-[1.3fr_0.85fr_1fr]">
              <section className="flex min-h-0 flex-col rounded-2xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <h2 className="text-sm font-semibold">{t("charts.quality.title")}</h2>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {t("charts.quality.subtitle")}
                </p>
                <div className="mt-2 min-h-0 flex-1">
                  <DashboardEChart option={qualityTrendOption} hasData={qualityTrendItems.length > 0} emptyLabel={t("states.empty")} />
                </div>
              </section>

              <section className="flex min-h-0 flex-col rounded-2xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <h2 className="text-sm font-semibold">{t("charts.runStatuses.title")}</h2>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {t("charts.runStatuses.subtitle")}
                </p>
                <div className="mt-2 min-h-0 flex-1">
                  <DashboardEChart option={runStatusOption} hasData={statusItems.length > 0} emptyLabel={t("states.empty")} />
                </div>
              </section>

              <section className="flex min-h-0 flex-col rounded-2xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <h2 className="text-sm font-semibold">{t("charts.suppliers.title")}</h2>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {t("charts.suppliers.subtitle", { generatedAt: formatCompactTimestamp(data.generated_at) })}
                </p>
                <div className="mt-2 min-h-0 flex-1">
                  <DashboardEChart option={supplierQualityOption} hasData={supplierQualityItems.length > 0} emptyLabel={t("states.empty")} />
                </div>
              </section>
            </div>
          </div>
        ) : null}
      </AsyncState>
    </section>
  );
}
