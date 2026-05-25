"use client";

import { CheckCircle2, LoaderCircle, PauseCircle, StopCircle, Timer, Unplug, X, type LucideIcon } from "lucide-react";
import { createPortal } from "react-dom";
import type { CSSProperties } from "react";
import { useTranslations } from "next-intl";

import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import type {
  AutoDbRemoteQuota,
  AutoDbTecdocBatchRun,
  AutoDbTecdocBatchSummary,
} from "@/features/backoffice/types/backoffice";

const REMOTE_QUOTA_DISPLAY_LIMIT = 3332;

function toCount(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatDateTime(value: string | null | undefined, locale: string): string {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "—";
  }
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return normalized;
  }
  return new Intl.DateTimeFormat(locale || "uk", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function resolveStepMarkerStyle(index: number): CSSProperties {
  if (index === 0) {
    return {
      width: "0.875rem",
      height: "0.875rem",
      borderRadius: "9999px",
      border: "2px solid #2563eb",
      backgroundColor: "#2563eb",
      boxShadow: "0 0 0 4px rgba(37,99,235,.2)",
    };
  }
  return {
    width: "0.875rem",
    height: "0.875rem",
    borderRadius: "9999px",
    border: "2px solid #94a3b8",
    backgroundColor: "#e2e8f0",
  };
}

function buildTimelineEvents(
  run: AutoDbTecdocBatchRun,
  locale: string,
  t: ReturnType<typeof useTranslations>,
): Array<{ id: string; title: string; time: string; details: string[] }> {
  const summary = (run.summary || {}) as AutoDbTecdocBatchSummary;
  const events: Array<{ id: string; title: string; time: string; details: string[] }> = [];

  const startedAt = run.started_at || summary.started_at || null;
  if (startedAt) {
    events.push({
      id: "started",
      title: t("batchHistory.timeline.started"),
      time: formatDateTime(startedAt, locale),
      details: [
        t("batchHistory.timeline.limit", { count: toCount(summary.requested_limit) }),
      ],
    });
  }

  if (toCount(summary.selected) > 0) {
    events.push({
      id: "selected",
      title: t("batchHistory.timeline.selected"),
      time: formatDateTime(summary.last_heartbeat_at || startedAt, locale),
      details: [
        t("batchHistory.timeline.selectedCount", { count: toCount(summary.selected) }),
      ],
    });
  }

  const processed = toCount(summary.processed);
  const bound = toCount(summary.bound);
  const failed = toCount(summary.failed);
  if (processed > 0 || run.status === "running") {
    const progressLine = [
      t("batchHistory.timeline.processed", { count: processed }),
      t("batchHistory.timeline.linked", { count: bound }),
      t("batchHistory.timeline.errors", { count: failed }),
    ].join(" • ");
    const stage = String(summary.stage || "").trim();
    const stageDetails: string[] = [];
    if (stage === "waiting_quota_recovery") {
      stageDetails.push(t("batchHistory.timeline.waitingQuota"));
    } else if (stage === "waiting_remote_retry") {
      stageDetails.push(t("batchHistory.timeline.waitingRemoteRetry"));
    }
    events.push({
      id: "progress",
      title: run.status === "running" ? t("batchHistory.timeline.inProgress") : t("batchHistory.timeline.progress"),
      time: formatDateTime(summary.last_heartbeat_at || startedAt, locale),
      details: [progressLine, ...stageDetails],
    });
  }

  const finishedAt = run.finished_at || summary.finished_at || null;
  if (finishedAt) {
    const stoppedReason = String(summary.stopped_reason || "").trim();
    const finishedTitle =
      stoppedReason === "manual_stop"
        ? t("batchHistory.timeline.stopped")
        : failed > 0
          ? t("batchHistory.timeline.finishedWithIssues")
          : t("batchHistory.timeline.finished");

    events.push({
      id: "finished",
      title: finishedTitle,
      time: formatDateTime(finishedAt, locale),
      details: String(summary.last_error || "").trim() ? [t("batchHistory.timeline.lastError", { value: String(summary.last_error || "") })] : [],
    });
  }

  return events.length ? events : [{
    id: "empty",
    title: t("batchHistory.timeline.noSteps"),
    time: "—",
    details: [],
  }];
}

function resolveRunStatusLabel({
  run,
  summary,
  isRunning,
  t,
}: {
  run: AutoDbTecdocBatchRun | null;
  summary: AutoDbTecdocBatchSummary;
  isRunning: boolean;
  t: ReturnType<typeof useTranslations>;
}): { tone: "blue" | "gray" | "success" | "warning"; label: string; icon: LucideIcon } {
  if (isRunning) {
    const stage = String(summary.stage || "").trim();
    if (stage === "waiting_quota_recovery") {
      return { tone: "warning", label: t("batchHistory.badges.quotaPause"), icon: Timer };
    }
    if (stage === "waiting_remote_retry") {
      return { tone: "warning", label: t("batchHistory.badges.remotePause"), icon: Unplug };
    }
    return { tone: "blue", label: t("batchHistory.status.running"), icon: LoaderCircle };
  }
  if (!run) {
    return { tone: "gray", label: t("batchHistory.status.idle"), icon: PauseCircle };
  }

  const stopReason = String(summary.stopped_reason || "").trim();
  if (stopReason === "manual_stop") {
    return { tone: "warning", label: t("batchHistory.status.stopped"), icon: StopCircle };
  }
  return { tone: "success", label: t("batchHistory.status.completed"), icon: CheckCircle2 };
}

export function AutoDbBatchHistoryModal({
  isOpen,
  locale,
  run,
  remoteQuota,
  isRunning,
  onClose,
}: {
  isOpen: boolean;
  locale: string;
  run: AutoDbTecdocBatchRun | null;
  remoteQuota: AutoDbRemoteQuota | null;
  isRunning: boolean;
  onClose: () => void;
}) {
  const t = useTranslations("backoffice.autodbMatching");

  if (!isOpen || typeof document === "undefined") {
    return null;
  }

  const summary = (run?.summary || {}) as AutoDbTecdocBatchSummary;
  const requestedLimit = toCount(summary.requested_limit);
  const selected = toCount(summary.selected);
  const processed = toCount(summary.processed);
  const processedInCycle = toCount(summary.processed_in_cycle);
  const isContinuous = Boolean(summary.continuous);
  const processedTarget = selected || requestedLimit;
  const linked = toCount(summary.bound);
  const errors = toCount(summary.failed);
  const rawQuotaUsed = toCount(remoteQuota?.estimated_queries_used);
  const rawQuotaLimit = toCount(remoteQuota?.estimated_limit_per_hour);
  const quotaLimit = rawQuotaLimit > 0 ? Math.min(rawQuotaLimit, REMOTE_QUOTA_DISPLAY_LIMIT) : 0;
  const quotaUsed = quotaLimit > 0 ? Math.min(rawQuotaUsed, quotaLimit) : rawQuotaUsed;
  const status = resolveRunStatusLabel({ run, summary, isRunning, t });
  const statusIconClassName =
    isRunning && status.icon === LoaderCircle
      ? "[&>svg]:animate-spin"
      : isRunning && status.icon === Timer
        ? "autodb-batch-quota-alarm"
        : "";

  const timelineEvents = run ? buildTimelineEvents(run, locale, t) : [];

  return createPortal(
    <div className="fixed inset-0 z-[1400] flex items-center justify-center bg-black/45 px-3 py-4" onClick={onClose}>
      <div
        className="w-full max-w-2xl overflow-hidden rounded-xl border shadow-2xl"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
        onClick={(event) => event.stopPropagation()}
      >
        <header
          className="flex items-center justify-between border-b px-4 py-3"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
        >
          <div className="min-w-0">
            <p className="text-sm font-semibold">{t("batchHistory.title")}</p>
            <p className="mt-0.5 truncate text-xs" style={{ color: "var(--muted)" }}>
              {run ? t("batchHistory.subtitle", { id: run.id.slice(0, 8) }) : t("batchHistory.subtitleEmpty")}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <StatusChip
              tone={status.tone}
              icon={status.icon}
              className={statusIconClassName}
            >
              {status.label}
            </StatusChip>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              aria-label={t("actions.close")}
            >
              <X className="size-4" />
            </button>
          </div>
        </header>

        <div className="max-h-[75vh] overflow-y-auto px-4 py-4">
          <div className="mb-4">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              <MetricCard
                label={t("batchHistory.metrics.processed")}
                value={isContinuous ? `${processedInCycle}/${processedTarget || "—"}` : `${processed}/${processedTarget || "—"}`}
              />
              <MetricCard label={t("batchHistory.metrics.linked")} value={linked} />
              <MetricCard label={t("batchHistory.metrics.errors")} value={errors} />
              <MetricCard label={t("batchHistory.metrics.quota")} value={`${quotaUsed}/${quotaLimit || "—"}`} />
            </div>
          </div>

          {!run ? (
            <p className="text-sm" style={{ color: "var(--muted)" }}>{t("batchHistory.empty")}</p>
          ) : (
            <ol className="grid gap-0">
              {timelineEvents.map((event, index) => {
                const isFirst = index === 0;
                const isLast = index === timelineEvents.length - 1;
                return (
                  <li key={event.id} className="relative pb-5 pl-11 last:pb-0">
                    {!isFirst ? (
                      <span aria-hidden="true" className="absolute left-4 top-0 h-[1.125rem] w-px -translate-x-1/2" style={{ backgroundColor: "#cbd5e1" }} />
                    ) : null}
                    {!isLast ? (
                      <span aria-hidden="true" className="absolute bottom-0 left-4 top-[1.125rem] w-px -translate-x-1/2" style={{ backgroundColor: "#cbd5e1" }} />
                    ) : null}
                    <span aria-hidden="true" className="absolute left-4 top-1.5 inline-flex h-6 w-6 -translate-x-1/2 items-center justify-center bg-transparent">
                      <span style={resolveStepMarkerStyle(index)} />
                    </span>
                    <div className="grid gap-2 rounded-lg border px-3 py-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <p className="text-sm font-semibold">{event.title}</p>
                        <span className="text-xs" style={{ color: "var(--muted)" }}>{event.time}</span>
                      </div>
                      {event.details.length ? (
                        <ul className="grid gap-1 text-xs" style={{ color: "var(--muted)" }}>
                          {event.details.map((detail, itemIndex) => (
                            <li key={`${event.id}-${itemIndex}`}>{detail}</li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <article className="w-full rounded-lg border px-2.5 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <p className="text-[11px] uppercase tracking-[0.11em]" style={{ color: "var(--muted)" }}>{label}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </article>
  );
}
