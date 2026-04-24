"use client";

import { useEffect, useRef } from "react";

type EChartInstance = {
  setOption: (option: object) => void;
  resize: () => void;
  dispose: () => void;
};

export function EchartsPanel({
  option,
  hasData,
  emptyLabel,
  className = "h-[280px] w-full",
}: {
  option: object;
  hasData: boolean;
  emptyLabel: string;
  className?: string;
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
        className="flex h-[240px] items-center justify-center rounded-xl border text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }}
      >
        {emptyLabel}
      </div>
    );
  }

  return <div ref={chartRef} className={className} />;
}
