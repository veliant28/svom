import type { ReactNode } from "react";

export function PaymentMethodCard({
  title,
  icon,
  selected,
  onClick,
}: {
  title: string;
  hint: string;
  icon: ReactNode;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <div>
      <button
        type="button"
        className="inline-flex h-11 w-full items-center justify-center gap-1.5 rounded-md border px-3 text-sm font-semibold transition"
        style={{
          borderColor: selected ? "var(--accent)" : "var(--border)",
          backgroundColor: "var(--surface-2)",
          boxShadow: selected ? "0 0 0 2px var(--accent)" : "none",
        }}
        onClick={onClick}
      >
        {icon}
        <span className="text-center leading-tight text-[var(--text)]">{title}</span>
      </button>
    </div>
  );
}
