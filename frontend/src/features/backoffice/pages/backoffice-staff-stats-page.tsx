"use client";

import { useCallback, useMemo, useRef, useEffect } from "react";
import { Activity, RefreshCw, TicketPercent, Truck } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";

import { getBackofficeStaffActivity } from "@/features/backoffice/api/backoffice-api";
import { OperationsRoleSwitcher } from "@/features/backoffice/components/dashboard/operations-role-switcher";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeStaffActivityPayload, BackofficeStaffActivityRole } from "@/features/backoffice/types/backoffice";

type EChartInstance = {
  setOption: (option: object) => void;
  resize: () => void;
  dispose: () => void;
};

function StaffStatsEChart({
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
        className="flex h-full min-h-[220px] items-center justify-center rounded-xl border text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }}
      >
        {emptyLabel}
      </div>
    );
  }

  return <div ref={chartRef} className="h-[260px] w-full" />;
}

function StaffKpiCard({
  title,
  value,
  subtitle,
  icon,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: ReactNode;
}) {
  return (
    <article className="rounded-2xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] uppercase tracking-[0.14em]" style={{ color: "var(--muted)" }}>
          {title}
        </p>
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          {icon}
        </span>
      </div>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {subtitle}
      </p>
    </article>
  );
}

function formatCompactDateTime(raw: string | null): string {
  if (!raw) {
    return "-";
  }
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

export function BackofficeStaffStatsPage({ role }: { role: BackofficeStaffActivityRole }) {
  const t = useTranslations("backoffice.dashboard");
  const queryFn = useCallback((token: string) => getBackofficeStaffActivity(token, { role, days: 14 }), [role]);
  const { data, isLoading, error, refetch } = useBackofficeQuery<BackofficeStaffActivityPayload>(queryFn, [role]);

  const roleAccent = role === "manager" ? "#2563eb" : "#ea580c";
  const roleAccentSoft = role === "manager" ? "rgba(37,99,235,0.16)" : "rgba(234,88,12,0.16)";
  const numberFormatter = useMemo(() => new Intl.NumberFormat(), []);
  const formatNumber = useCallback((value: number) => numberFormatter.format(Number.isFinite(value) ? value : 0), [numberFormatter]);

  const trendOption = useMemo(() => ({
    animationDuration: 500,
    grid: { left: 20, right: 18, top: 24, bottom: 18, containLabel: true },
    tooltip: { trigger: "axis" },
    legend: { top: 0, right: 0, textStyle: { color: "#64748b", fontSize: 11 } },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: (data?.chart_by_day ?? []).map((item) => item.date.slice(5)),
      axisLabel: { color: "#64748b", fontSize: 11 },
      axisLine: { lineStyle: { color: "#cbd5e1" } },
    },
    yAxis: {
      type: "value",
      minInterval: 1,
      axisLabel: { color: "#64748b", fontSize: 11 },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    series: [
      {
        name: t("staff.metrics.ttnActions"),
        type: "line",
        smooth: true,
        data: (data?.chart_by_day ?? []).map((item) => item.ttn_actions),
        lineStyle: { color: roleAccent, width: 2 },
        areaStyle: { color: roleAccentSoft },
        itemStyle: { color: roleAccent },
      },
      {
        name: t("staff.metrics.loyaltyIssued"),
        type: "line",
        smooth: true,
        data: (data?.chart_by_day ?? []).map((item) => item.loyalty_issued),
        lineStyle: { color: "#16a34a", width: 2 },
        areaStyle: { color: "rgba(22,163,74,0.10)" },
        itemStyle: { color: "#16a34a" },
      },
      {
        name: t("staff.metrics.priceChanges"),
        type: "line",
        smooth: true,
        data: (data?.chart_by_day ?? []).map((item) => item.price_changes),
        lineStyle: { color: "#475569", width: 2 },
        areaStyle: { color: "rgba(71,85,105,0.10)" },
        itemStyle: { color: "#475569" },
      },
    ],
  }), [data?.chart_by_day, roleAccent, roleAccentSoft, t]);

  const topStaff = useMemo(() => (data?.staff ?? []).slice(0, 8).reverse(), [data?.staff]);
  const topStaffOption = useMemo(() => ({
    animationDuration: 500,
    grid: { left: 16, right: 16, top: 24, bottom: 16, containLabel: true },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: {
      type: "value",
      minInterval: 1,
      axisLabel: { color: "#64748b", fontSize: 11 },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    yAxis: {
      type: "category",
      data: topStaff.map((item) => item.staff_name || item.staff_email),
      axisLabel: { color: "#475569", fontSize: 11 },
      axisLine: { lineStyle: { color: "#cbd5e1" } },
    },
    series: [
      {
        name: t("staff.metrics.actionsTotal"),
        type: "bar",
        barWidth: 12,
        data: topStaff.map((item) => item.actions_total),
        itemStyle: { color: roleAccent, borderRadius: [0, 5, 5, 0] },
      },
    ],
  }), [roleAccent, t, topStaff]);

  return (
    <section>
      <PageHeader
        title={t("staff.titleAll")}
        description={t("staff.subtitle")}
        switcher={(
          <OperationsRoleSwitcher
            activeTab={role}
            dashboardHref="/backoffice"
            managersHref="/backoffice/operations/managers"
            operatorsHref="/backoffice/operations/operators"
            dashboardLabel={t("staff.roles.dashboard")}
            managersLabel={t("staff.roles.managers")}
            operatorsLabel={t("staff.roles.operators")}
            ariaLabel={t("staff.switcherAriaLabel")}
          />
        )}
        actions={(
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
        )}
      />

      <AsyncState isLoading={isLoading} error={error} empty={!data} emptyLabel={t("states.empty")}>
        {data ? (
          <div className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StaffKpiCard
                title={t("staff.kpis.staffTotal")}
                value={formatNumber(data.kpis.staff_total)}
                subtitle={t("staff.kpis.withActivity", { count: formatNumber(data.kpis.with_activity_total) })}
                icon={<Activity className="h-4 w-4" />}
              />
              <StaffKpiCard
                title={t("staff.kpis.actionsTotal")}
                value={formatNumber(data.kpis.actions_total)}
                subtitle={t("staff.kpis.ttnTotal", { count: formatNumber(data.kpis.ttn_actions_total) })}
                icon={<Truck className="h-4 w-4" />}
              />
              <StaffKpiCard
                title={t("staff.kpis.loyaltyTotal")}
                value={formatNumber(data.kpis.loyalty_issued_total)}
                subtitle={t("staff.kpis.priceChangesTotal", { count: formatNumber(data.kpis.price_changes_total) })}
                icon={<TicketPercent className="h-4 w-4" />}
              />
              <StaffKpiCard
                title={t("staff.kpis.period")}
                value={t("staff.kpis.periodDays", { days: data.days })}
                subtitle={t("staff.kpis.generatedAt", { value: formatCompactDateTime(data.generated_at) })}
                icon={<RefreshCw className="h-4 w-4" />}
              />
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <section className="rounded-2xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <h2 className="text-sm font-semibold">{t("staff.charts.dailyTitle")}</h2>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {t("staff.charts.dailySubtitle")}
                </p>
                <div className="mt-2">
                  <StaffStatsEChart option={trendOption} hasData={(data.chart_by_day ?? []).length > 0} emptyLabel={t("states.empty")} />
                </div>
              </section>

              <section className="rounded-2xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <h2 className="text-sm font-semibold">{t("staff.charts.staffTitle")}</h2>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {t("staff.charts.staffSubtitle")}
                </p>
                <div className="mt-2">
                  <StaffStatsEChart option={topStaffOption} hasData={topStaff.length > 0} emptyLabel={t("states.empty")} />
                </div>
              </section>
            </div>

            <section className="rounded-2xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <h2 className="text-sm font-semibold">{t("staff.table.title")}</h2>
              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                {t("staff.table.subtitle")}
              </p>
              <div className="mt-3">
                <BackofficeTable
                  rows={data.staff}
                  emptyLabel={t("states.empty")}
                  columns={[
                    {
                      key: "staff",
                      label: t("staff.table.columns.staff"),
                      render: (item) => (
                        <div className="grid gap-0.5">
                          <span className="font-semibold">{item.staff_name || "-"}</span>
                          <span className="text-xs" style={{ color: "var(--muted)" }}>
                            {item.staff_email}
                          </span>
                        </div>
                      ),
                    },
                    {
                      key: "actions",
                      label: t("staff.table.columns.actions"),
                      render: (item) => formatNumber(item.actions_total),
                    },
                    {
                      key: "ttn",
                      label: t("staff.table.columns.ttn"),
                      render: (item) => `${formatNumber(item.ttn_actions)} / ${formatNumber(item.ttn_orders)}`,
                    },
                    {
                      key: "loyalty",
                      label: t("staff.table.columns.loyalty"),
                      render: (item) => `${formatNumber(item.loyalty_issued)} / ${formatNumber(item.loyalty_used)}`,
                    },
                    {
                      key: "discount",
                      label: t("staff.table.columns.discountSum"),
                      render: (item) => item.loyalty_discount_sum,
                    },
                    {
                      key: "pricing",
                      label: t("staff.table.columns.pricing"),
                      render: (item) => (
                        <span>
                          {formatNumber(item.price_changes)} ({formatNumber(item.price_manual)}/{formatNumber(item.price_import)}/{formatNumber(item.price_auto)})
                        </span>
                      ),
                    },
                    {
                      key: "last",
                      label: t("staff.table.columns.lastActivity"),
                      render: (item) => formatCompactDateTime(item.last_activity_at),
                    },
                  ]}
                />
              </div>
            </section>
          </div>
        ) : null}
      </AsyncState>
    </section>
  );
}
