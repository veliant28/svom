export function VchasnoField({
  label,
  children,
  hint,
  error,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
  error?: string;
}) {
  return (
    <label className="grid gap-1">
      <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>{label}</span>
      {children}
      {hint ? <span className="text-xs" style={{ color: "var(--muted)" }}>{hint}</span> : null}
      {error ? <span className="text-xs" style={{ color: "#b91c1c" }}>{error}</span> : null}
    </label>
  );
}

export function VchasnoToggleField({ label, value, onToggle }: { label: string; value: boolean; onToggle: () => void }) {
  return (
    <label className="inline-flex items-center gap-2 text-sm font-medium">
      <input type="checkbox" checked={value} onChange={onToggle} />
      <span>{label}</span>
    </label>
  );
}

export function VchasnoStatusRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <p className="text-[11px]" style={{ color: "var(--muted)" }}>{label}</p>
      <p className={`mt-1 text-sm font-medium text-[var(--text)] ${mono ? "font-mono" : ""}`}>{value || "-"}</p>
    </div>
  );
}
