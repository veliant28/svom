"use client";

import { useEffect, useRef } from "react";

type EChartInstance = {
  setOption: (option: object, opts?: { notMerge?: boolean; lazyUpdate?: boolean }) => void;
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
  const chartInstanceRef = useRef<EChartInstance | null>(null);

  useEffect(() => {
    const onResize = () => {
      chartInstanceRef.current?.resize();
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
    };
  }, []);

  useEffect(() => {
    let disposed = false;

    async function renderChart() {
      if (!hasData || !chartRef.current) {
        chartInstanceRef.current?.dispose();
        chartInstanceRef.current = null;
        return;
      }

      const echarts = await import("echarts");
      if (disposed || !chartRef.current) {
        return;
      }

      if (!chartInstanceRef.current) {
        chartInstanceRef.current = echarts.init(chartRef.current);
      }

      const optionWithTooltip = {
        ...option,
        tooltip: {
          ...(option as { tooltip?: Record<string, unknown> }).tooltip,
          confine: true,
          appendToBody: true,
        },
      };
      chartInstanceRef.current.setOption(optionWithTooltip, { notMerge: true, lazyUpdate: true });
      chartInstanceRef.current.resize();
    }

    void renderChart();

    return () => {
      disposed = true;
    };
  }, [hasData, option]);

  useEffect(() => {
    return () => {
      chartInstanceRef.current?.dispose();
      chartInstanceRef.current = null;
    };
  }, []);

  if (!hasData) {
    return (
      <div
        className={`flex items-center justify-center rounded-xl border text-sm ${className}`}
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }}
      >
        {emptyLabel}
      </div>
    );
  }

  return <div ref={chartRef} className={className} />;
}
