"use client";

import { useEffect, useRef } from "react";

type ChartInstance = {
  setOption: (option: object) => void;
  resize: () => void;
  dispose: () => void;
};

export function SecurityChart({ option, emptyLabel, hasData }: { option: object; emptyLabel: string; hasData: boolean }) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!hasData) {
      return;
    }
    let chart: ChartInstance | null = null;
    let disposed = false;
    async function mount() {
      if (!ref.current) {
        return;
      }
      const echarts = await import("echarts");
      if (disposed || !ref.current) {
        return;
      }
      chart = echarts.init(ref.current);
      chart.setOption(option);
    }
    void mount();
    const onResize = () => chart?.resize();
    window.addEventListener("resize", onResize);
    return () => {
      disposed = true;
      window.removeEventListener("resize", onResize);
      chart?.dispose();
    };
  }, [hasData, option]);

  if (!hasData) {
    return (
      <div className="flex h-full min-h-[160px] items-center justify-center rounded-xl border text-sm" style={{ borderColor: "var(--border)", color: "var(--muted)" }}>
        {emptyLabel}
      </div>
    );
  }
  return <div ref={ref} className="h-full min-h-[160px] w-full overflow-hidden" />;
}
