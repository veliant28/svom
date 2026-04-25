import { X } from "lucide-react";

type VchasnoCodesModalRow = {
  code: string;
  label: string;
};

export function VchasnoCodesModal({
  isOpen,
  title,
  rows,
  rightColumnLabel,
  codeLabel,
  closeLabel,
  onClose,
}: {
  isOpen: boolean;
  title: string;
  rows: readonly VchasnoCodesModalRow[];
  rightColumnLabel: string;
  codeLabel: string;
  closeLabel: string;
  onClose: () => void;
}) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={closeLabel}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-lg rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <div className="mb-3 flex items-start justify-between gap-2">
          <h2 className="text-sm font-semibold">{title}</h2>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onClose}
            aria-label={closeLabel}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <table className="min-w-full border-separate border-spacing-0 text-sm">
            <thead style={{ backgroundColor: "var(--surface-2)", color: "var(--muted)" }}>
              <tr>
                <th className="px-3 py-2 text-left font-medium">{codeLabel}</th>
                <th className="px-3 py-2 text-left font-medium">{rightColumnLabel}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.code}>
                  <td className="border-t px-3 py-2 font-mono" style={{ borderColor: "var(--border)" }}>{row.code}</td>
                  <td className="border-t px-3 py-2" style={{ borderColor: "var(--border)" }}>{row.label}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
