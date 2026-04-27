import { Minus, Plus } from "lucide-react";

function stepNumberValue(value: string, delta: number, min: number): string {
  const parsed = Number(value);
  const current = Number.isFinite(parsed) && parsed >= min ? parsed : min;
  return String(Math.max(min, current + delta));
}

function normalizeNumberInput(value: string): string {
  return value.replace(/\D/g, "");
}

export function NumberStepperField({
  label,
  value,
  min = 1,
  step = 1,
  disabled = false,
  onChange,
}: {
  label: string;
  value: string;
  min?: number;
  step?: number;
  disabled?: boolean;
  onChange: (next: string) => void;
}) {
  return (
    <div className="inline-grid w-fit gap-1 text-xs">
      <span>{label}</span>
      <div
        className="inline-flex h-9 w-fit items-center rounded-full border px-1"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      >
        <button
          type="button"
          disabled={disabled}
          className="inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors hover:opacity-90 disabled:opacity-50"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          aria-label={`${label} -`}
          onClick={() => onChange(stepNumberValue(value, -step, min))}
        >
          <Minus className="h-3.5 w-3.5" />
        </button>
        <input
          type="text"
          inputMode="numeric"
          autoComplete="off"
          value={value}
          disabled={disabled}
          aria-label={label}
          className="h-7 w-16 border-0 bg-transparent px-1 text-center text-sm font-semibold outline-none disabled:opacity-70"
          onChange={(event) => onChange(normalizeNumberInput(event.target.value))}
          onKeyDown={(event) => {
            if (event.key === "ArrowUp") {
              event.preventDefault();
              onChange(stepNumberValue(value, step, min));
            } else if (event.key === "ArrowDown") {
              event.preventDefault();
              onChange(stepNumberValue(value, -step, min));
            }
          }}
        />
        <button
          type="button"
          disabled={disabled}
          className="inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors hover:opacity-90 disabled:opacity-50"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          aria-label={`${label} +`}
          onClick={() => onChange(stepNumberValue(value, step, min))}
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
