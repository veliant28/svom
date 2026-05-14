"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Clock3, Package, Tags } from "lucide-react";
import { useTranslations } from "next-intl";

import { getAutoDbMatchingRemoteQuota } from "@/features/backoffice/api/backoffice-api";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { EchartsPanel } from "@/features/backoffice/components/widgets/echarts-panel";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { AutoDbRemoteQuota } from "@/features/backoffice/types/backoffice";

import { formatCountdown, Panel } from "./ui";

function statusLabel(status: string, t: ReturnType<typeof useTranslations>) {
  if (status === "quota_paused") {
    return t("quota.statusPaused");
  }
  if (status === "warning") {
    return t("quota.statusWarning");
  }
  return t("quota.statusOk");
}

function statusTone(status: string): "success" | "warning" | "error" {
  if (status === "quota_paused") {
    return "error";
  }
  if (status === "warning") {
    return "warning";
  }
  return "success";
}

function resolvePausedTimerSeconds(quota: AutoDbRemoteQuota | null, nowMs: number): number | null {
  if (!quota || quota.status !== "quota_paused") {
    return null;
  }

  if (quota.cooldown_until) {
    const cooldownTs = new Date(quota.cooldown_until).getTime();
    if (Number.isFinite(cooldownTs)) {
      return Math.max(0, Math.floor((cooldownTs - nowMs) / 1000));
    }
  }

  return Math.max(0, Math.floor(quota.seconds_until_reset || 0));
}

type QuotaPoint = { ts: number; percent: number; qpm: number; cumulative: number };

export function AutoDbQuotaCard({
  onQuotaChange,
  refreshNonce = 0,
  quotaMeta,
}: {
  onQuotaChange?: (quota: AutoDbRemoteQuota | null) => void;
  refreshNonce?: number;
  quotaMeta?: {
    mappedBrands: number;
    totalBrands: number;
    linkedProducts: number;
    totalProducts: number;
  };
}) {
  const t = useTranslations("backoffice.autodbMatching");
  const tDashboard = useTranslations("backoffice.dashboard");
  const queryFn = useCallback((token: string) => getAutoDbMatchingRemoteQuota(token), []);
  const { data, isLoading, error, refetch } = useBackofficeQuery<AutoDbRemoteQuota>(queryFn);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [chartNowMs, setChartNowMs] = useState(() => Date.now());

  useEffect(() => {
    onQuotaChange?.(data ?? null);
  }, [data, onQuotaChange]);

  useEffect(() => {
    const poll = window.setInterval(() => {
      void refetch();
    }, 10_000);
    return () => window.clearInterval(poll);
  }, [refetch]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const chartClock = window.setInterval(() => {
      setChartNowMs(Date.now());
    }, 5_000);
    return () => window.clearInterval(chartClock);
  }, []);

  useEffect(() => {
    if (refreshNonce <= 0) {
      return;
    }
    void refetch();
  }, [refreshNonce, refetch]);

  const used = Number(data?.estimated_queries_used ?? 0);
  const limit = Math.max(1, Number(data?.estimated_limit_per_hour ?? 1));
  const usagePercent = Math.min(100, Math.max(0, Number(data?.usage_percent ?? (used / limit) * 100)));
  const tone = statusTone(data?.status ?? "ok");
  const secondsLeft = resolvePausedTimerSeconds(data ?? null, nowMs);

  const recentPoints = useMemo(() => data?.recent_points ?? [], [data?.recent_points]);
  const windowMs = 60 * 60 * 1000;
  const rangeEndMs = chartNowMs;
  const rangeStartMs = chartNowMs - windowMs;

  const chartOption = useMemo(() => {
    const parsedRows: QuotaPoint[] = recentPoints
      .map((point) => {
        const ts = new Date(point.timestamp).getTime();
        const percent = limit > 0 ? Math.min(100, (Number(point.cumulative_used || 0) / limit) * 100) : 0;
        return { ts, percent, qpm: Number(point.query_count || 0), cumulative: Number(point.cumulative_used || 0) };
      })
      .filter((point) => Number.isFinite(point.ts))
      .sort((a, b) => a.ts - b.ts)
      .filter((point) => point.ts >= rangeStartMs && point.ts <= rangeEndMs);

    const lineRows: Array<[number, number, number, number]> = parsedRows.map((point) => [point.ts, point.percent, point.qpm, point.cumulative]);
    const lastPercent = lineRows.length > 0 ? lineRows[lineRows.length - 1][1] : usagePercent;
    const lastQpm = lineRows.length > 0 ? lineRows[lineRows.length - 1][2] : 0;
    const lastCumulative = lineRows.length > 0 ? lineRows[lineRows.length - 1][3] : used;

    if (lineRows.length === 0) {
      lineRows.push([rangeStartMs, usagePercent, 0, used]);
    } else if (lineRows[0][0] > rangeStartMs) {
      lineRows.unshift([rangeStartMs, lineRows[0][1], lineRows[0][2], lineRows[0][3]]);
    }
    lineRows.push([rangeEndMs, lastPercent, lastQpm, lastCumulative]);

    return {
      animationDuration: 220,
      animationDurationUpdate: 900,
      animationEasingUpdate: "linear",
      grid: { left: 14, right: 14, top: 12, bottom: 24, containLabel: true },
      tooltip: {
        trigger: "axis",
        formatter: (params: Array<{ data?: [number, number, number, number] }>) => {
          const first = params[0]?.data;
          if (!first) {
            return "";
          }
          const [time, percent, qpm, cumulative] = first;
          return [
            `${new Date(time).toLocaleTimeString()}`,
            `${t("quota.queriesPerMinute")}: ${qpm}`,
            `Load: ${Number(percent).toFixed(1)}%`,
            `Used: ${cumulative}/${limit}`,
          ].join("<br/>");
        },
      },
      xAxis: {
        type: "time",
        boundaryGap: false,
        min: rangeStartMs,
        max: rangeEndMs,
        splitNumber: 8,
        axisLabel: {
          color: "#64748b",
          fontSize: 10,
          margin: 6,
          hideOverlap: false,
          showMinLabel: true,
          showMaxLabel: true,
          formatter: (value: number | string) => {
            const dt = new Date(value);
            if (Number.isNaN(dt.getTime())) {
              return "";
            }
            const hh = String(dt.getHours()).padStart(2, "0");
            const mm = String(dt.getMinutes()).padStart(2, "0");
            return `${hh}:${mm}`;
          },
        },
        axisTick: { show: true },
        axisLine: { lineStyle: { color: "#cbd5e1" } },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLabel: { color: "#64748b", fontSize: 10, formatter: "{value}%" },
        splitLine: { lineStyle: { color: "#e2e8f0" } },
      },
      series: [
        {
          name: "Quota load",
          type: "line",
          smooth: 0.25,
          showSymbol: false,
          lineStyle: { width: 2, color: tone === "error" ? "#e11d48" : tone === "warning" ? "#ca8a04" : "#2563eb" },
          areaStyle: {
            color:
              tone === "error"
                ? "rgba(225,29,72,0.14)"
                : tone === "warning"
                  ? "rgba(202,138,4,0.14)"
                  : "rgba(37,99,235,0.14)",
          },
          data: lineRows,
        },
      ],
    };
  }, [limit, rangeEndMs, rangeStartMs, recentPoints, t, tone, usagePercent, used]);

  const timerValue = secondsLeft === null ? tDashboard("cards.unprocessedOrdersTimerIdle") : formatCountdown(secondsLeft);
  const timerLabel = tDashboard("cards.unprocessedOrdersTimer", { value: timerValue });
  const timerTone = secondsLeft === null ? "success" : tone;
  const mappedBrands = Math.max(0, Number(quotaMeta?.mappedBrands ?? 0));
  const totalBrands = Math.max(0, Number(quotaMeta?.totalBrands ?? 0));
  const linkedProducts = Math.max(0, Number(quotaMeta?.linkedProducts ?? 0));
  const totalProducts = Math.max(0, Number(quotaMeta?.totalProducts ?? 0));

  return (
    <Panel className="grid gap-3 overflow-hidden">
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2">
        <h2 className="text-sm font-semibold">{t("quota.title")}</h2>
        <div className="flex items-center justify-center gap-2">
          <BackofficeTooltip
            content={t("quota.mappedBrandsTooltip", { mapped: mappedBrands, total: totalBrands })}
            placement="top"
            align="center"
            wrapperClassName="inline-flex"
            tooltipClassName="whitespace-nowrap"
          >
            <span>
              <BackofficeStatusChip tone="teal" icon={Tags} className="cursor-pointer">
                {mappedBrands}/{totalBrands}
              </BackofficeStatusChip>
            </span>
          </BackofficeTooltip>

          <BackofficeTooltip
            content={t("quota.linkedProductsTooltip", { linked: linkedProducts, total: totalProducts })}
            placement="top"
            align="center"
            wrapperClassName="inline-flex"
            tooltipClassName="whitespace-nowrap"
          >
            <span>
              <BackofficeStatusChip tone="blue" icon={Package} className="cursor-pointer">
                {linkedProducts}/{totalProducts}
              </BackofficeStatusChip>
            </span>
          </BackofficeTooltip>
        </div>
        <div className="flex justify-end">
          <BackofficeStatusChip tone={tone}>{statusLabel(data?.status ?? "ok", t)}</BackofficeStatusChip>
        </div>
      </div>

      <div className="flex items-center justify-between gap-2">
        <BackofficeStatusChip
          tone={timerTone}
          icon={Clock3}
          palette="countdown"
          className={timerTone === "warning" || timerTone === "error" ? "animate-pulse" : ""}
        >
          {timerLabel}
        </BackofficeStatusChip>
        <BackofficeStatusChip tone="info" icon={Activity}>
          {usagePercent.toFixed(1)}%
        </BackofficeStatusChip>
      </div>

      <EchartsPanel option={chartOption} hasData={!isLoading && !error} emptyLabel={error || t("states.empty")} className="h-[240px] w-full" />
    </Panel>
  );
}
