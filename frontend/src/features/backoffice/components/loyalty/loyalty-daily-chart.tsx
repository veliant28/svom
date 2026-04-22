"use client";

import { useEffect, useRef } from "react";

type LoyaltyDailyChartProps = {
  items: Array<{ date: string; total: number }>;
  emptyLabel: string;
  className?: string;
  emptyClassName?: string;
};

export function LoyaltyDailyChart({
  items,
  emptyLabel,
  className = "h-[190px] w-full",
  emptyClassName = "h-[170px]",
}: LoyaltyDailyChartProps) {
  const chartRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let chart: { dispose: () => void; resize: () => void; setOption: (option: object) => void } | null = null;
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
      chart.setOption({
        grid: { left: 18, right: 12, top: 20, bottom: 20, containLabel: true },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "line" },
        },
        xAxis: {
          type: "category",
          data: items.map((item) => item.date.slice(5)),
          axisLabel: {
            color: "#64748b",
            fontSize: 11,
          },
          axisLine: { lineStyle: { color: "#cbd5e1" } },
        },
        yAxis: {
          type: "value",
          minInterval: 1,
          axisLabel: {
            color: "#64748b",
            fontSize: 11,
          },
          splitLine: { lineStyle: { color: "#e2e8f0" } },
        },
        series: [
          {
            type: "line",
            smooth: true,
            symbolSize: 6,
            data: items.map((item) => item.total),
            lineStyle: {
              color: "#2563eb",
              width: 2,
            },
            areaStyle: {
              color: "rgba(37,99,235,0.15)",
            },
            itemStyle: {
              color: "#2563eb",
            },
          },
        ],
      });
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
  }, [items]);

  if (!items.length) {
    return (
      <div
        className={`flex items-center justify-center rounded-xl border text-sm ${emptyClassName}`}
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }}
      >
        {emptyLabel}
      </div>
    );
  }

  return <div ref={chartRef} className={className} />;
}
