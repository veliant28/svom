"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, LoaderCircle, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";

import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { getSupportWallboard } from "@/features/support/api/support-api";
import { SupportStatusChip } from "@/features/support/components/support-status-chip";
import { SupportWallboardChart } from "@/features/support/components/support-wallboard-chart";
import { useSupportSocket } from "@/features/support/hooks/use-support-socket";
import type { SupportRealtimeEvent, SupportWallboardSnapshot } from "@/features/support/types";

const COUNT_KEYS = [
  "new",
  "open",
  "resolved",
  "closed",
  "unassigned",
  "online_operators",
  "active_threads",
] as const;

export function SupportWallboardPage() {
  const t = useTranslations("backoffice.common.support");
  const { token } = useAuth();
  const { showApiError } = useBackofficeFeedback();
  const [snapshot, setSnapshot] = useState<SupportWallboardSnapshot | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      return;
    }
    try {
      setSnapshot(await getSupportWallboard(token));
    } catch (error) {
      showApiError(error, t("messages.loadWallboardFailed"));
    }
  }, [showApiError, t, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const wallboardSocket = useSupportSocket({
    token,
    path: "/ws/support/wallboard/",
    enabled: Boolean(token),
    onEvent: (event: SupportRealtimeEvent) => {
      if (event.type === "support.wallboard.updated") {
        setSnapshot(event.payload);
      }
    },
  });

  const chartItems = useMemo(() => {
    if (!snapshot) {
      return [];
    }
    return [
      { label: t("wallboard.counts.new"), value: snapshot.counts.new },
      { label: t("wallboard.counts.open"), value: snapshot.counts.open },
      { label: t("wallboard.counts.resolved"), value: snapshot.counts.resolved },
    ];
  }, [snapshot, t]);

  return (
    <section className="grid min-w-0 gap-4 overflow-x-hidden">
      <PageHeader
        title={t("wallboard.title")}
        description={t("wallboard.subtitle")}
        actions={(
          <div className="inline-flex items-center gap-2">
            <BackofficeStatusChip
              tone={wallboardSocket.connectionState === "open" ? "success" : "warning"}
              icon={wallboardSocket.connectionState === "open" ? CheckCircle2 : LoaderCircle}
              className={wallboardSocket.connectionState === "open" ? "" : "animate-pulse"}
            >
              {wallboardSocket.connectionState === "open" ? t("states.realtimeConnected") : t("states.realtimeReconnecting")}
            </BackofficeStatusChip>
            <button
              type="button"
              className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void load();
              }}
            >
              <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
              {t("actions.refresh")}
            </button>
          </div>
        )}
      />

      <div className="grid min-w-0 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {snapshot ? COUNT_KEYS.map((key) => (
          <div key={key} className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <p className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
              {t(`wallboard.counts.${key}`)}
            </p>
            <p className="mt-2 text-3xl font-bold">{snapshot.counts[key]}</p>
          </div>
        )) : null}
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(280px,360px)]">
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <SupportWallboardChart items={chartItems} />
        </div>
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <p className="text-sm font-semibold">{t("wallboard.oldestWaiting")}</p>
          {snapshot?.oldest_waiting ? (
            <div className="mt-3 grid gap-2">
              <p className="text-sm font-semibold">{snapshot.oldest_waiting.subject}</p>
              <SupportStatusChip status={snapshot.oldest_waiting.status} />
              <p className="text-xs" style={{ color: "var(--muted)" }}>{snapshot.oldest_waiting.customer.full_name}</p>
            </div>
          ) : (
            <p className="mt-3 text-sm" style={{ color: "var(--muted)" }}>{t("states.emptyThreads")}</p>
          )}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <p className="text-sm font-semibold">{t("wallboard.operators")}</p>
          <div className="mt-3 grid gap-2">
            {snapshot?.threads_per_operator.map((row) => (
              <div key={row.user.id} className="flex items-center justify-between rounded-lg border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                <div>
                  <p className="text-sm font-semibold">{row.user.full_name}</p>
                  <p className="text-xs" style={{ color: row.user.is_online ? "#166534" : "var(--muted)" }}>
                    {row.user.is_online ? t("shared.online") : t("shared.offline")}
                  </p>
                </div>
                <p className="text-lg font-bold">{row.active_threads}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <p className="text-sm font-semibold">{t("wallboard.latest")}</p>
          <div className="mt-3 grid gap-2">
            {snapshot?.latest_active_threads.map((thread) => (
              <div key={thread.id} className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-semibold">{thread.subject}</p>
                  <SupportStatusChip status={thread.status} />
                </div>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{thread.customer.full_name}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
