"use client";

import { AlertTriangle, Ban, KeyRound, ShieldAlert, Siren, TimerReset } from "lucide-react";
import { useMemo } from "react";

import { ActionIconButton } from "@/features/backoffice/components/widgets/action-icon-button";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { SecurityThreatBadge } from "@/features/backoffice/security/components/security-badges";
import { SecurityChart } from "@/features/backoffice/security/components/security-chart";
import { SecurityBlockTimer } from "@/features/backoffice/security/components/security-timer";
import type { SecurityBlock, SecurityEvent, SecuritySummary, SecurityTimeseries } from "@/features/backoffice/security/types/security.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

function KpiCard({ label, value, icon: Icon }: { label: string; value: number; icon: typeof ShieldAlert }) {
  return (
    <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color: "var(--muted)" }}>
          {label}
        </p>
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <Icon className="size-4" />
        </span>
      </div>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </article>
  );
}

function Panel({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`flex min-h-0 flex-col rounded-xl border p-3 ${className}`} style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="mb-2 text-sm font-semibold">{title}</p>
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}

function CriticalEventsList({ rows, t, onOpen }: { rows: SecurityEvent[]; t: Translator; onOpen: (actorId: string) => void }) {
  if (!rows.length) {
    return <p className="text-sm" style={{ color: "var(--muted)" }}>{t("empty.criticalEvents")}</p>;
  }
  return (
    <div className="max-h-[150px] overflow-y-auto">
      {rows.map((event) => (
        <div key={event.id} className="grid grid-cols-[1fr_auto] gap-2 border-b py-2 last:border-b-0" style={{ borderColor: "var(--border)" }}>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{event.source_ip || event.actor_source || t("sourceKind.unknown")}</p>
            <p className="truncate text-xs" style={{ color: "var(--muted)" }}>{t(`eventTypes.${event.event_type}`)}</p>
          </div>
          <ActionIconButton
            label={t("actions.view")}
            icon={ShieldAlert}
            disabled={!event.actor_id}
            onClick={() => event.actor_id && onOpen(event.actor_id)}
          />
        </div>
      ))}
    </div>
  );
}

function ActiveBlocksList({ rows, t, onRelease }: { rows: SecurityBlock[]; t: Translator; onRelease: (block: SecurityBlock) => void }) {
  if (!rows.length) {
    return <p className="text-sm" style={{ color: "var(--muted)" }}>{t("empty.activeBlocks")}</p>;
  }
  return (
    <div className="max-h-[150px] overflow-y-auto">
      {rows.map((block) => (
        <div key={block.id} className="grid grid-cols-[1fr_auto] gap-2 border-b py-2 last:border-b-0" style={{ borderColor: "var(--border)" }}>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{block.actor_source || block.value}</p>
            <div className="mt-1"><SecurityThreatBadge level={block.actor_threat_level} t={t} /></div>
            <div className="mt-1"><SecurityBlockTimer block={block} t={t} /></div>
          </div>
          <button
            type="button"
            className="h-8 rounded-md border px-2 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={() => onRelease(block)}
          >
            {t("actions.release")}
          </button>
        </div>
      ))}
    </div>
  );
}

export function SecurityDashboard({
  summary,
  timeseries,
  isLoading,
  error,
  t,
  onRelease,
  onOpenActorById,
}: {
  summary: SecuritySummary | null;
  timeseries: SecurityTimeseries | null;
  isLoading: boolean;
  error: string | null;
  t: Translator;
  onRelease: (block: SecurityBlock) => void;
  onOpenActorById: (actorId: string) => void;
}) {
  const translateEventType = useMemo(() => (eventType: string) => {
    try {
      return t(`eventTypes.${eventType}`);
    } catch {
      return eventType;
    }
  }, [t]);

  const seriesOption = useMemo(() => ({
    grid: { left: 32, right: 16, top: 16, bottom: 24 },
    tooltip: { trigger: "axis", appendToBody: true, confine: false },
    xAxis: { type: "category", data: (timeseries?.events_by_hour ?? []).map((row) => new Date(row.bucket).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })) },
    yAxis: { type: "value", min: 0 },
    series: [{ type: "line", smooth: true, data: (timeseries?.events_by_hour ?? []).map((row) => row.total), areaStyle: {} }],
    color: ["#dc2626"],
  }), [timeseries?.events_by_hour]);

  const donutOption = useMemo(() => ({
    tooltip: { trigger: "item", appendToBody: true, confine: false },
    series: [{ type: "pie", radius: ["48%", "76%"], label: { show: false }, data: (timeseries?.events_by_type ?? []).map((row) => ({ name: translateEventType(row.event_type), value: row.total })) }],
    color: ["#dc2626", "#f59e0b", "#2563eb", "#16a34a", "#64748b"],
  }), [timeseries?.events_by_type, translateEventType]);

  return (
    <AsyncState isLoading={isLoading} error={error} empty={false} emptyLabel={t("empty.dashboard")}>
      <div className="grid h-[calc(100vh-9rem)] min-h-0 grid-rows-[auto_minmax(0,1fr)_auto] gap-3 overflow-hidden">
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-6">
          <KpiCard label={t("dashboard.kpis.activeBlocks")} value={summary?.kpis.active_blocks ?? 0} icon={Ban} />
          <KpiCard label={t("dashboard.kpis.suspiciousSources")} value={summary?.kpis.suspicious_sources ?? 0} icon={ShieldAlert} />
          <KpiCard label={t("dashboard.kpis.blocked24h")} value={summary?.kpis.blocked_24h ?? 0} icon={TimerReset} />
          <KpiCard label={t("dashboard.kpis.failedLogins")} value={summary?.kpis.failed_logins ?? 0} icon={KeyRound} />
          <KpiCard label={t("dashboard.kpis.rateLimit")} value={summary?.kpis.rate_limit_events ?? 0} icon={AlertTriangle} />
          <KpiCard label={t("dashboard.kpis.criticalThreats")} value={summary?.kpis.critical_threats ?? 0} icon={Siren} />
        </div>

        <div className="grid min-h-0 grid-cols-1 gap-3 xl:grid-cols-[1.2fr_.75fr_.75fr_.75fr]">
          <Panel title={t("dashboard.charts.events")} className="overflow-hidden">
            <SecurityChart option={seriesOption} hasData={Boolean(timeseries?.events_by_hour?.length)} emptyLabel={t("empty.chart")} />
          </Panel>
          <Panel title={t("dashboard.charts.types")} className="overflow-hidden">
            <SecurityChart option={donutOption} hasData={Boolean(timeseries?.events_by_type?.length)} emptyLabel={t("empty.chart")} />
          </Panel>
          <Panel title={t("dashboard.charts.sources")}>
            <div className="h-full min-h-0 space-y-2 overflow-y-auto text-sm">
              {(timeseries?.top_sources ?? []).map((row) => (
                <div key={row.source_ip || "unknown"} className="flex justify-between gap-2">
                  <span className="truncate">{row.source_ip || t("sourceKind.unknown")}</span>
                  <strong>{row.total}</strong>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title={t("dashboard.charts.endpoints")}>
            <div className="h-full min-h-0 space-y-2 overflow-y-auto text-sm">
              {(timeseries?.top_endpoints ?? []).map((row) => (
                <div key={row.endpoint} className="flex justify-between gap-2">
                  <span className="truncate">{row.endpoint}</span>
                  <strong>{row.total}</strong>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div className="grid min-h-0 grid-cols-1 gap-3 xl:grid-cols-2">
          <Panel title={t("dashboard.latestCritical")}>
            <CriticalEventsList rows={summary?.latest_critical_events ?? []} t={t} onOpen={onOpenActorById} />
          </Panel>
          <Panel title={t("dashboard.activeBlocks")}>
            <ActiveBlocksList rows={summary?.active_blocks ?? []} t={t} onRelease={onRelease} />
          </Panel>
        </div>
      </div>
    </AsyncState>
  );
}
