"use client";

import { useEffect, useRef } from "react";

export function SupportWallboardChart({ items }: { items: Array<{ label: string; value: number }> }) {
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
        grid: { left: 12, right: 12, top: 16, bottom: 20, containLabel: true },
        xAxis: { type: "category", data: items.map((item) => item.label), axisLabel: { color: "#64748b", fontSize: 11 } },
        yAxis: { type: "value", minInterval: 1, axisLabel: { color: "#64748b", fontSize: 11 } },
        series: [{ type: "bar", data: items.map((item) => item.value), itemStyle: { color: "#2563eb", borderRadius: [6, 6, 0, 0] } }],
        tooltip: { trigger: "axis" },
      });
    }

    void mount();
    const onResize = () => chart?.resize();
    window.addEventListener("resize", onResize);
    return () => {
      disposed = true;
      window.removeEventListener("resize", onResize);
      chart?.dispose();
    };
  }, [items]);

  return <div ref={chartRef} className="h-[220px] w-full" />;
}
