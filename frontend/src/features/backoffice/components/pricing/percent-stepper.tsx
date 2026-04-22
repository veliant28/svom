"use client";

import { Minus, Plus } from "lucide-react";

type PercentStepperProps = {
  value: number;
  onChange: (next: number) => void;
  min?: number;
  max?: number;
  step?: number;
  minusLabel: string;
  plusLabel: string;
  inputLabel: string;
};

function clampPercent(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.max(min, Math.min(max, value));
}

function parsePercentInput(raw: string, min: number, max: number, fallback: number): number {
  const normalized = raw.trim().replace(",", ".").replace(/[^0-9.]/g, "");
  if (!normalized) {
    return min;
  }
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return clampPercent(parsed, min, max);
}

export function PercentStepper({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  minusLabel,
  plusLabel,
  inputLabel,
}: PercentStepperProps) {
  const safeValue = clampPercent(value, min, max);

  return (
    <div
      className="inline-flex h-9 items-center rounded-full border px-1"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
    >
      <button
        type="button"
        className="inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors hover:opacity-90"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        aria-label={minusLabel}
        onClick={() => onChange(clampPercent(safeValue - step, min, max))}
      >
        <Minus className="h-3.5 w-3.5" />
      </button>

      <label className="relative inline-flex items-center px-1">
        <input
          type="text"
          inputMode="decimal"
          autoComplete="off"
          value={safeValue}
          aria-label={inputLabel}
          className="h-7 w-16 border-0 bg-transparent px-1 pr-4 text-center text-sm font-semibold outline-none"
          onChange={(event) => onChange(parsePercentInput(event.target.value, min, max, safeValue))}
        />
        <span className="pointer-events-none absolute right-1 text-xs" style={{ color: "var(--muted)" }}>
          %
        </span>
      </label>

      <button
        type="button"
        className="inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors hover:opacity-90"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        aria-label={plusLabel}
        onClick={() => onChange(clampPercent(safeValue + step, min, max))}
      >
        <Plus className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
