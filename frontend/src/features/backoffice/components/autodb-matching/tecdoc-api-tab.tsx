"use client";

import {
  AlertTriangle,
  CheckCircle2,
  LoaderCircle,
  Minus,
  PauseCircle,
  Play,
  Plus,
  StopCircle,
  Timer,
  Unplug,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { EchartsPanel } from "@/features/backoffice/components/widgets/echarts-panel";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import type { useAutoDbTecdocApiBatchMonitor } from "@/features/backoffice/hooks/use-autodb-tecdoc-api-batch-monitor";
import type {
  AutoDbRemoteQuota,
  AutoDbTecdocBatchRun,
  AutoDbTecdocBatchSummary,
} from "@/features/backoffice/types/backoffice";

import { formatCountdown, formatDateTime } from "./ui";

const REMOTE_QUOTA_DISPLAY_LIMIT = 3332;

function toCount(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function resolveLiveResetSeconds(quota: AutoDbRemoteQuota | null, nowMs: number): number {
  if (!quota || quota.status !== "quota_paused") {
    return 0;
  }

  const cooldownUntil = String(quota.cooldown_until || "").trim();
  if (cooldownUntil) {
    const cooldownTs = new Date(cooldownUntil).getTime();
    if (Number.isFinite(cooldownTs)) {
      return Math.max(0, Math.floor((cooldownTs - nowMs) / 1000));
    }
  }

  return Math.max(0, Math.floor(toCount(quota.seconds_until_reset)));
}

function resolveQuotaMetrics(quota: AutoDbRemoteQuota | null): { used: number; limit: number; remaining: number } {
  const rawUsed = Math.max(toCount(quota?.estimated_queries_used), 0);
  const limitFromField = Math.max(toCount(quota?.estimated_limit_per_hour), 0);
  const limitFromRemaining = rawUsed + Math.max(toCount(quota?.estimated_queries_remaining), 0);
  const usagePercent = Math.max(0, Math.min(toCount(quota?.usage_percent), 100));
  const limitFromPercent = usagePercent > 0 ? Math.round((rawUsed * 100) / usagePercent) : 0;
  const inferredLimit = Math.max(limitFromField, limitFromRemaining, limitFromPercent, 1);
  const limit = Math.max(1, Math.min(inferredLimit, REMOTE_QUOTA_DISPLAY_LIMIT));
  const used = Math.min(rawUsed, limit);
  const remaining = Math.max(limit - used, 0);
  return { used, limit, remaining };
}

type PieLabelLayoutParams = {
  align?: "left" | "center" | "right";
  dataIndex?: number;
  viewRect?: { x: number; y: number; width: number; height: number };
  labelRect?: { x: number; y: number; width: number; height: number };
  rect?: { x: number; y: number; width: number; height: number };
};

function normalizeAngle(angle: number): number {
  const twoPi = Math.PI * 2;
  let normalized = angle % twoPi;
  if (normalized <= -Math.PI) {
    normalized += twoPi;
  } else if (normalized > Math.PI) {
    normalized -= twoPi;
  }
  return normalized;
}

function shiftPieLabelAlongArcNearEdge(params: PieLabelLayoutParams, sliceValues: number[]): {
  x?: number;
  y?: number;
  hideOverlap: false;
  moveOverlap: "shiftY";
} {
  const labelRect = params.labelRect;
  const pieRect = params.rect;
  const viewRect = params.viewRect || params.rect;
  if (!labelRect || !pieRect || !viewRect) {
    return { hideOverlap: false, moveOverlap: "shiftY" };
  }

  // Keep label text untouched and line length unchanged; only rotate label
  // around the pie (clockwise/counter-clockwise) when it gets clipped by edge.
  const minX = viewRect.x + 6;
  const maxX = Math.max((viewRect.x + viewRect.width) - 6, minX + labelRect.width + 4);
  const leftOverflow = Math.max(minX - labelRect.x, 0);
  const rightOverflow = Math.max((labelRect.x + labelRect.width) - maxX, 0);
  if (leftOverflow <= 0 && rightOverflow <= 0) {
    return { hideOverlap: false, moveOverlap: "shiftY" };
  }

  const centerX = pieRect.x + (pieRect.width / 2);
  const centerY = pieRect.y + (pieRect.height / 2);
  const labelCenterX = labelRect.x + (labelRect.width / 2);
  const labelCenterY = labelRect.y + (labelRect.height / 2);
  const dx = labelCenterX - centerX;
  const dy = labelCenterY - centerY;
  const radius = Math.max(Math.hypot(dx, dy), 1);
  const sourceAngle = Math.atan2(dy, dx);

  const total = Math.max(sliceValues.reduce((acc, item) => acc + Math.max(item, 0), 0), 1);
  const dataIndex = Math.max(0, Math.min(Number(params.dataIndex ?? 0), sliceValues.length - 1));
  const currentSliceValue = Math.max(sliceValues[dataIndex] ?? 0, 0);
  const beforeSliceValue = sliceValues
    .slice(0, dataIndex)
    .reduce((acc, item) => acc + Math.max(item, 0), 0);
  const fullCircle = Math.PI * 2;
  const sliceStart = (-Math.PI / 2) + ((beforeSliceValue / total) * fullCircle);
  const sliceSpan = (currentSliceValue / total) * fullCircle;
  const sliceEnd = sliceStart + sliceSpan;
  const sliceCenter = sliceStart + (sliceSpan / 2);
  const sourceAngleUnwrapped = sourceAngle + (Math.round((sliceCenter - sourceAngle) / fullCircle) * fullCircle);
  const slicePad = Math.min(0.14, Math.max(0.02, sliceSpan * 0.2));
  const lowerBound = sliceStart + slicePad;
  const upperBound = sliceEnd - slicePad;
  const boundedSource =
    sliceSpan > (slicePad * 2)
      ? Math.max(lowerBound, Math.min(upperBound, sourceAngleUnwrapped))
      : sliceCenter;
  const evaluateOverflow = (angleUnwrapped: number) => {
    const nx = centerX + (Math.cos(angleUnwrapped) * radius) - (labelRect.width / 2);
    const left = Math.max(minX - nx, 0);
    const right = Math.max((nx + labelRect.width) - maxX, 0);
    return { total: left + right, x: nx, y: centerY + (Math.sin(angleUnwrapped) * radius) - (labelRect.height / 2) };
  };

  const sourceOverflow = evaluateOverflow(boundedSource);
  let bestAngle = boundedSource;
  let best = sourceOverflow;
  if (sourceOverflow.total > 0 && sliceSpan > (slicePad * 2)) {
    const steps = 32;
    for (let i = 0; i <= steps; i += 1) {
      const ratio = i / steps;
      const probe = lowerBound + ((upperBound - lowerBound) * ratio);
      const evaluated = evaluateOverflow(probe);
      if (evaluated.total < best.total) {
        best = evaluated;
        bestAngle = probe;
        continue;
      }
      if (evaluated.total === best.total) {
        const currentDistance = Math.abs(probe - boundedSource);
        const bestDistance = Math.abs(bestAngle - boundedSource);
        if (currentDistance < bestDistance) {
          best = evaluated;
          bestAngle = probe;
        }
      }
    }
  }

  const normalizedBestAngle = normalizeAngle(bestAngle);
  const nextCenterX = centerX + (Math.cos(normalizedBestAngle) * radius);
  const nextCenterY = centerY + (Math.sin(normalizedBestAngle) * radius);

  return {
    x: nextCenterX - (labelRect.width / 2),
    y: nextCenterY - (labelRect.height / 2),
    hideOverlap: false,
    moveOverlap: "shiftY",
  };
}

function resolveRunStatusChip({
  run,
  summary,
  isRunning,
  t,
}: {
  run: AutoDbTecdocBatchRun | null;
  summary: AutoDbTecdocBatchSummary;
  isRunning: boolean;
  t: ReturnType<typeof useTranslations>;
}): { tone: "blue" | "gray" | "success" | "warning"; label: string; icon: LucideIcon; animationClass: string } {
  const stage = String(summary.stage || "").trim();
  const runStatus = String(run?.status || "").trim().toLowerCase();
  const summaryRunning = Boolean(summary.running);
  const effectivelyRunning = isRunning || summaryRunning || runStatus === "running";
  const waitingQuota = stage === "waiting_quota_recovery";
  const waitingRemote = stage === "waiting_remote_retry";

  if (effectivelyRunning || waitingQuota || waitingRemote) {
    if (stage === "waiting_quota_recovery") {
      return { tone: "warning", label: t("tecdocApi.status.waitingQuota"), icon: Timer, animationClass: "[&>svg]:animate-spin" };
    }
    if (stage === "waiting_remote_retry") {
      return { tone: "warning", label: t("tecdocApi.status.waitingRemote"), icon: Unplug, animationClass: "[&>svg]:animate-pulse" };
    }
    return { tone: "blue", label: t("tecdocApi.status.running"), icon: LoaderCircle, animationClass: "[&>svg]:animate-spin" };
  }

  if (!run) {
    return { tone: "gray", label: t("tecdocApi.status.idle"), icon: PauseCircle, animationClass: "" };
  }

  const stopReason = String(summary.stopped_reason || "").trim();
  if (stopReason === "manual_stop") {
    return { tone: "warning", label: t("tecdocApi.status.stopped"), icon: StopCircle, animationClass: "" };
  }

  const failed = toCount(summary.failed);
  if (failed > 0) {
    return { tone: "warning", label: t("tecdocApi.status.finishedWithIssues"), icon: AlertTriangle, animationClass: "" };
  }

  return { tone: "success", label: t("tecdocApi.status.finished"), icon: CheckCircle2, animationClass: "" };
}

function chartSeries({ run, quota, t }: { run: AutoDbTecdocBatchRun | null; quota: AutoDbRemoteQuota | null; t: ReturnType<typeof useTranslations> }) {
  const summary = (run?.summary || {}) as AutoDbTecdocBatchSummary;
  const requestedLimit = Math.max(toCount(summary.requested_limit), 1);
  const selected = Math.max(toCount(summary.selected), requestedLimit);
  const processed = toCount(summary.processed);
  const linked = toCount(summary.bound);
  const failed = toCount(summary.failed);
  const remaining = Math.max(selected - processed, 0);

  const progressOption = {
    animationDuration: 260,
    grid: { left: 20, right: 20, top: 18, bottom: 18, containLabel: true },
    xAxis: {
      type: "value",
      axisLabel: { color: "#64748b", fontSize: 11 },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
      min: 0,
      max: requestedLimit + 1,
    },
    yAxis: {
      type: "category",
      data: [
        t("tecdocApi.charts.remaining"),
        t("tecdocApi.charts.processed"),
        t("tecdocApi.charts.linked"),
        t("tecdocApi.charts.failed"),
      ],
      axisLabel: { color: "#475569", fontSize: 11 },
    },
    series: [
      {
        type: "bar",
        clip: false,
        data: [remaining, processed, linked, failed],
        itemStyle: {
          color: (args: { dataIndex: number }) => ["#94a3b8", "#0ea5e9", "#16a34a", "#f97316"][args.dataIndex] || "#94a3b8",
          borderRadius: [0, 6, 6, 0],
        },
        label: { show: true, position: "right", color: "#0f172a", fontSize: 11 },
      },
    ],
  };

  const quotaMetrics = resolveQuotaMetrics(quota);
  const limit = quotaMetrics.limit;
  const used = quotaMetrics.used;
  const remainingQuota = quotaMetrics.remaining;
  const quotaSlices = [used, remainingQuota];

  const quotaOption = {
    animationDuration: 260,
    legend: {
      bottom: 0,
      textStyle: { color: "#475569", fontSize: 11 },
    },
    series: [
      {
        name: t("tecdocApi.charts.quotaTitle"),
        type: "pie",
        left: 0,
        right: 0,
        top: 2,
        bottom: 26,
        radius: ["54%", "76%"],
        center: ["50%", "44%"],
        avoidLabelOverlap: false,
        label: {
          show: true,
          position: "outside",
          alignTo: "labelLine",
          margin: 2,
          bleedMargin: 4,
          formatter: "{d}%",
          color: "#0f172a",
          fontSize: 12,
          fontWeight: 500,
        },
        labelLine: { show: true, length: 12, length2: 10, smooth: false },
        labelLayout: (params: PieLabelLayoutParams) => shiftPieLabelAlongArcNearEdge(params, quotaSlices),
        data: [
          { value: used, name: t("tecdocApi.charts.quotaUsed"), itemStyle: { color: "#0ea5e9" } },
          { value: remainingQuota, name: t("tecdocApi.charts.quotaLeft"), itemStyle: { color: "#22c55e" } },
        ],
      },
    ],
  };

  return {
    progressOption,
    quotaOption,
    progressHasData: Boolean(run),
    quotaHasData: limit > 0,
  };
}

type TecdocApiBatchMonitor = ReturnType<typeof useAutoDbTecdocApiBatchMonitor>;

export function AutoDbMatchingTecdocApiTab({ monitor }: { monitor: TecdocApiBatchMonitor }) {
  const t = useTranslations("backoffice.autodbMatching");
  const [nowMs, setNowMs] = useState(() => Date.now());
  const run = monitor.run;
  const summary = (run?.summary || {}) as AutoDbTecdocBatchSummary;
  const running = monitor.isRunning;
  const charts = chartSeries({ run, quota: monitor.remoteQuota, t });

  const selected = Math.max(toCount(summary.selected), toCount(summary.requested_limit));
  const processed = toCount(summary.processed);
  const linked = toCount(summary.bound);
  const failed = toCount(summary.failed);
  const quotaMetrics = resolveQuotaMetrics(monitor.remoteQuota);
  const quotaUsed = quotaMetrics.used;
  const quotaLimit = quotaMetrics.limit;
  const quotaPaused = monitor.remoteQuota?.status === "quota_paused";
  const isLoading = monitor.isLoading;
  const batchStatus = resolveRunStatusChip({ run, summary, isRunning: running, t });
  const liveResetSeconds = resolveLiveResetSeconds(monitor.remoteQuota ?? null, nowMs);

  useEffect(() => {
    const timerId = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);
    return () => window.clearInterval(timerId);
  }, []);

  return (
    <section className="grid h-[calc(100vh-11rem)] min-h-[560px] grid-rows-[auto_minmax(0,1fr)] gap-3 overflow-hidden">
      <article className="rounded-2xl border p-3 lg:p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip
              tone={batchStatus.tone}
              icon={batchStatus.icon}
              className={batchStatus.animationClass}
            >
              {batchStatus.label}
            </StatusChip>
            <StatusChip tone="success" icon={CheckCircle2}>{t("status.tecdoc.tecdoc")}</StatusChip>
          </div>

          <div className="flex items-center gap-2">
            <div className="inline-flex items-center rounded-full border p-1" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <button
                type="button"
                className="inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors hover:opacity-90 disabled:opacity-50"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                aria-label={t("actions.batchSizeMinus")}
                onClick={() => monitor.setBatchSize(monitor.batchSize - 10)}
                disabled={monitor.isSubmitting || running || monitor.batchSize <= 10}
              >
                <Minus className="h-3.5 w-3.5" />
              </button>
              <span className="inline-flex h-7 min-w-[2rem] items-center justify-center px-2 text-xs font-semibold tabular-nums">{monitor.batchSize}</span>
              <button
                type="button"
                className="inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors hover:opacity-90 disabled:opacity-50"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                aria-label={t("actions.batchSizePlus")}
                onClick={() => monitor.setBatchSize(monitor.batchSize + 10)}
                disabled={monitor.isSubmitting || running || monitor.batchSize >= 1000}
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>

            <BackofficeTooltip content={t("tecdocApi.actions.run")}
              placement="top" align="center" wrapperClassName="inline-flex">
              <button
                type="button"
                className={`inline-flex h-10 w-10 items-center justify-center rounded-md border transition-colors disabled:opacity-60 ${running ? "animate-pulse" : ""}`}
                style={{ borderColor: "#047857", backgroundColor: "#059669", color: "#ffffff" }}
                onClick={() => {
                  void monitor.runBatch();
                }}
                disabled={monitor.isSubmitting || running}
                aria-label={t("tecdocApi.actions.run")}
              >
                {running ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              </button>
            </BackofficeTooltip>

            <BackofficeTooltip content={t("tecdocApi.actions.stop")}
              placement="top" align="center" wrapperClassName="inline-flex">
              <button
                type="button"
                className="inline-flex h-10 w-10 items-center justify-center rounded-md border transition-colors disabled:opacity-60"
                style={{ borderColor: "#b91c1c", backgroundColor: "#ef4444", color: "#ffffff" }}
                onClick={() => {
                  void monitor.stopBatch();
                }}
                disabled={monitor.isSubmitting || !running}
                aria-label={t("tecdocApi.actions.stop")}
              >
                <StopCircle className="h-4 w-4" />
              </button>
            </BackofficeTooltip>

          </div>
        </div>
      </article>

      <article className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-3 rounded-2xl border p-3 lg:p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
          <Metric label={t("tecdocApi.metrics.selected")} value={selected} />
          <Metric label={t("tecdocApi.metrics.processed")} value={`${processed}/${selected || "-"}`} />
          <Metric label={t("tecdocApi.metrics.linked")} value={linked} />
          <Metric label={t("tecdocApi.metrics.failed")} value={failed} />
          <Metric label={t("tecdocApi.metrics.quota")} value={`${quotaUsed}/${quotaLimit || "-"}`} />
        </div>

        <div className="min-h-0 grid gap-3 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="flex min-h-0 flex-col rounded-xl border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <p className="px-1 text-xs font-semibold uppercase tracking-[0.12em]" style={{ color: "var(--muted)" }}>{t("tecdocApi.charts.progressTitle")}</p>
            <div className="min-h-0 flex-1">
              <EchartsPanel
                option={charts.progressOption}
                hasData={charts.progressHasData}
                emptyLabel={isLoading ? t("states.loadingCandidates") : t("states.empty")}
                className="h-full w-full"
              />
            </div>
          </div>

          <div className="grid min-h-0 w-full grid-rows-[minmax(0,1fr)_auto] gap-2 lg:w-[22rem] lg:justify-self-end">
            <div className="flex min-h-0 flex-col rounded-xl border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <p className="px-1 text-xs font-semibold uppercase tracking-[0.12em]" style={{ color: "var(--muted)" }}>{t("tecdocApi.charts.quotaTitle")}</p>
              <div className="min-h-0 flex-1">
                <EchartsPanel
                  option={charts.quotaOption}
                  hasData={charts.quotaHasData}
                  emptyLabel={t("states.empty")}
                  className="h-full w-full"
                />
              </div>
            </div>

            <div className="rounded-xl border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <p className="text-xs" style={{ color: "var(--muted)" }}>{t("tecdocApi.meta.lastRun")}</p>
              <p className="mt-1 text-sm font-semibold break-all">{run?.id || "-"}</p>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs" style={{ color: "var(--muted)" }}>
                <div>
                  <p>{t("tecdocApi.meta.started")}</p>
                  <p className="font-medium" style={{ color: "var(--text)" }}>{formatDateTime(run?.started_at || summary.started_at)}</p>
                </div>
                <div>
                  <p>{t("tecdocApi.meta.finished")}</p>
                  <p className="font-medium" style={{ color: "var(--text)" }}>{formatDateTime(run?.finished_at || summary.finished_at)}</p>
                </div>
                <div>
                  <p>{t("tecdocApi.meta.heartbeat")}</p>
                  <p className="font-medium" style={{ color: "var(--text)" }}>{formatDateTime(summary.last_heartbeat_at)}</p>
                </div>
                <div>
                  <p>{t("tecdocApi.meta.reset")}</p>
                  <p className="font-medium" style={{ color: "var(--text)" }}>
                    {quotaPaused ? formatCountdown(liveResetSeconds) : t("tecdocApi.badges.quotaLive")}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </article>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <article className="rounded-lg border px-2.5 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <p className="text-[11px] uppercase tracking-[0.11em]" style={{ color: "var(--muted)" }}>{label}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </article>
  );
}
