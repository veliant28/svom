"use client";

import { useMemo } from "react";

import type { BackofficeSeoDashboard } from "@/features/backoffice/api/seo-api.types";
import { EchartsPanel } from "@/features/backoffice/components/widgets/echarts-panel";

export function GoogleAnalyticsChart({
  dashboard,
  t,
}: {
  dashboard: BackofficeSeoDashboard | null;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  const events = dashboard?.google_events_state ?? [];
  const enabledEvents = events.filter((event) => event.enabled).length;
  const disabledEvents = Math.max(0, events.length - enabledEvents);

  const option = useMemo(() => ({
    animationDuration: 400,
    tooltip: { trigger: "item" },
    legend: { bottom: 0, textStyle: { color: "#64748b", fontSize: 11 } },
    series: [
      {
        name: t("seo.google.events"),
        type: "pie",
        radius: ["45%", "72%"],
        center: ["50%", "45%"],
        label: { formatter: "{b}: {c}", color: "#334155", fontSize: 11 },
        data: [
          { value: enabledEvents, name: t("seo.google.enabledEvents"), itemStyle: { color: "#16a34a" } },
          { value: disabledEvents, name: t("seo.google.disabledEvents"), itemStyle: { color: "#f59e0b" } },
        ],
      },
    ],
  }), [disabledEvents, enabledEvents, t]);

  return (
    <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{t("seo.google.chartTitle")}</p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {t("seo.google.chartSubtitle")}
      </p>
      <div className="mt-3">
        <EchartsPanel option={option} hasData={events.length > 0} emptyLabel={t("seo.states.chartEmpty")} />
      </div>
      <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
        {t("seo.google.externalMetricsHint")}
      </p>
    </section>
  );
}
