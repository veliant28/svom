export function OrderViewValueField({
  label,
  value,
  mono = false,
  bold = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  bold?: boolean;
}) {
  return (
    <div className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <p className="text-[11px]" style={{ color: "var(--muted)" }}>{label}</p>
      <p className={`mt-1 text-sm ${mono ? "font-mono" : ""} ${bold ? "font-semibold" : "font-medium"} text-[var(--text)]`}>
        {value || "-"}
      </p>
    </div>
  );
}
