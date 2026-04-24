"use client";

import { useMemo } from "react";

import type { BackofficeSeoDashboard } from "@/features/backoffice/api/seo-api.types";
import { EchartsPanel } from "@/features/backoffice/components/widgets/echarts-panel";

export function SeoHealthChart({
  dashboard,
  t,
}: {
  dashboard: BackofficeSeoDashboard | null;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  const items = useMemo(() => dashboard?.seo_health_by_entity ?? [], [dashboard?.seo_health_by_entity]);

  const option = useMemo(() => {
    const labels = items.map((item) => t(`seo.entities.${item.entity}`));
    return {
      animationDuration: 400,
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: { bottom: 0, textStyle: { color: "#64748b", fontSize: 11 } },
      grid: { left: 26, right: 20, top: 20, bottom: 50, containLabel: true },
      xAxis: {
        type: "category",
        data: labels,
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
          name: t("seo.charts.ok"),
          type: "bar",
          stack: "health",
          data: items.map((item) => item.ok),
          itemStyle: { color: "#16a34a" },
        },
        {
          name: t("seo.charts.missingTitle"),
          type: "bar",
          stack: "health",
          data: items.map((item) => item.missing_title),
          itemStyle: { color: "#f59e0b" },
        },
        {
          name: t("seo.charts.missingDescription"),
          type: "bar",
          stack: "health",
          data: items.map((item) => item.missing_description),
          itemStyle: { color: "#ef4444" },
        },
      ],
    };
  }, [items, t]);

  return (
    <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{t("seo.charts.healthTitle")}</p>
      {!dashboard?.missing_meta_available ? (
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
          {t("seo.states.metaChecksUnavailable")}
        </p>
      ) : null}
      <div className="mt-3">
        <EchartsPanel option={option} hasData={items.length > 0} emptyLabel={t("seo.states.chartEmpty")} />
      </div>
    </section>
  );
}
