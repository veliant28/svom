import type { ReactNode } from "react";

export const fieldClass = "h-10 rounded-md border px-3 text-sm";
export const buttonClass = "inline-flex h-10 items-center justify-center rounded-md border px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60";
export const buttonCompactClass = "inline-flex h-8 items-center justify-center rounded-md border px-2.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60";
export const panelClass = "rounded-2xl border p-3 lg:p-4";
export const segmentedControlClass = "inline-flex items-center gap-2 rounded-xl border p-1";
export const segmentedControlButtonClass = "inline-flex h-10 items-center justify-center rounded-lg border px-4 text-sm font-semibold transition-colors";
export const compactText = { color: "var(--muted)" } as const;
export const surfaceStyle = { borderColor: "var(--border)", backgroundColor: "var(--surface)" } as const;
export const surface2Style = { borderColor: "var(--border)", backgroundColor: "var(--surface-2)" } as const;

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`${panelClass} ${className}`} style={surfaceStyle}>
      {children}
    </section>
  );
}

export function MiniKpi({ title, value, detail }: { title: string; value: ReactNode; detail?: ReactNode }) {
  return (
    <article className="rounded-2xl border p-3" style={surfaceStyle}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={compactText}>
        {title}
      </p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
      {detail ? (
        <p className="mt-1 truncate text-xs" style={compactText}>
          {detail}
        </p>
      ) : null}
    </article>
  );
}

export function StatusPill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "ok" | "warn" | "danger" }) {
  const colors = {
    neutral: { borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" },
    ok: { borderColor: "#bbf7d0", backgroundColor: "#f0fdf4", color: "#166534" },
    warn: { borderColor: "#fde68a", backgroundColor: "#fffbeb", color: "#92400e" },
    danger: { borderColor: "#fecdd3", backgroundColor: "#fff1f2", color: "#9f1239" },
  }[tone];
  return (
    <span className="inline-flex h-7 items-center rounded-md border px-2 text-xs font-semibold" style={colors}>
      {children}
    </span>
  );
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

export function formatCountdown(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds || 0));
  const minutes = Math.floor(safe / 60);
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  const restSeconds = safe % 60;
  return `${String(hours).padStart(2, "0")}:${String(restMinutes).padStart(2, "0")}:${String(restSeconds).padStart(2, "0")}`;
}
