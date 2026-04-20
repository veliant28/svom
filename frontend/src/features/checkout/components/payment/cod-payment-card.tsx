import { HandCoins } from "lucide-react";

export function CodPaymentCard({
  title,
  hint,
  selected,
  onSelect,
}: {
  title: string;
  hint: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <div>
      <button
        type="button"
        className="relative inline-flex h-11 w-full items-center justify-center gap-1.5 overflow-hidden rounded-md border px-3 transition"
        style={{
          borderColor: selected ? "var(--accent)" : "var(--border)",
          backgroundColor: "var(--surface-2)",
          boxShadow: selected ? "0 0 0 2px var(--accent)" : "none",
        }}
        onClick={onSelect}
        aria-pressed={selected}
        aria-label={title}
      >
        <HandCoins size={16} className="shrink-0 text-[var(--text)]" aria-hidden />
        <span className="text-center text-sm font-semibold leading-tight text-[var(--text)]">{title}</span>
      </button>
      {hint ? (
        <p className="mt-1 text-xs text-[var(--muted)]">{hint}</p>
      ) : null}
    </div>
  );
}
