type VchasnoPaymentMethodOption = {
  code: string;
  label: string;
};

function normalizeCode(value: string): string {
  return String(value || "").normalize("NFKC").trim().toUpperCase();
}

function hasCode(values: string[], code: string): boolean {
  const target = normalizeCode(code);
  return values.some((item) => normalizeCode(item) === target);
}

function toggleCode(values: string[], code: string): string[] {
  if (hasCode(values, code)) {
    return values.filter((item) => normalizeCode(item) !== normalizeCode(code));
  }
  return [...values, code];
}

export function VchasnoPaymentMethodsField({
  title,
  codesActionLabel,
  options,
  values,
  onChange,
  onOpenCodes,
}: {
  title: string;
  codesActionLabel: string;
  options: readonly VchasnoPaymentMethodOption[];
  values: string[];
  onChange: (next: string[]) => void;
  onOpenCodes: () => void;
}) {
  return (
    <section className="rounded-lg border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>{title}</p>
        <button
          type="button"
          className="text-xs font-semibold underline underline-offset-2"
          style={{ color: "var(--brand, #2563eb)" }}
          onClick={onOpenCodes}
        >
          {codesActionLabel}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {options.map((option) => (
          <label
            key={option.code}
            className="inline-flex min-h-9 items-center gap-2 rounded-md border px-2 py-1 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <input
              type="checkbox"
              checked={hasCode(values, option.code)}
              onChange={() => onChange(toggleCode(values, option.code))}
            />
            <span className="font-mono text-xs">{option.code}</span>
            <span className="leading-tight">{option.label}</span>
          </label>
        ))}
      </div>
    </section>
  );
}
